"""Explanations, live conditions, and geocoding endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_bundle, get_weather, mode_context
from app.api.envelope import AppError, Envelope, ok
from app.api.schemas import Condition, ConditionUsed, RoutesData
from app.domain.modes import ModeKey
from app.domain.timeutil import now_atlanta
from app.repositories.artifacts import Bundle
from app.repositories.history import HistoryRepository
from app.services.alert_voice import AlertAudio, AlertKind, resolve_alert_text
from app.services.explain.resolve import resolve_route_evidence, resolve_segment_evidence
from app.services.explain.service import ExplainService
from app.services.geocode import GeocodeService
from app.services.tts import VoiceChain
from app.services.weather import WeatherService

extras = APIRouter()
BundleDep = Annotated[Bundle, Depends(get_bundle)]
WeatherDep = Annotated[WeatherService, Depends(get_weather)]


class ExplainRequest(BaseModel):
    kind: Literal["segment", "route"]
    seg_id: int | None = Field(default=None, ge=0)
    route_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    t: str = Field(default="now", max_length=40)
    cond: Condition = "live"
    mode: ModeKey = "walk"  # segment explanations: which model seg_id belongs to


class ExplainData(BaseModel):
    text: str
    source: str


class GeoResultOut(BaseModel):
    label: str
    address: str
    lat: float
    lon: float
    in_coverage: bool


def _explainer(request: Request) -> ExplainService:
    service: ExplainService = request.app.state.explainer
    return service


def _routes_cache(request: Request) -> dict[str, RoutesData]:
    cache: dict[str, RoutesData] = request.app.state.routes_cache
    return cache


async def _explanation(
    req: ExplainRequest, request: Request, bundle: Bundle, weather: WeatherService
) -> ExplainData:
    service = _explainer(request)
    if req.kind == "route":
        resolved = resolve_route_evidence(
            _routes_cache(request), req.route_key, bundle.model_version
        )
    elif req.seg_id is None:
        raise AppError("BAD_REQUEST", "seg_id is required for segment explanations.", 422)
    else:
        resolved = await resolve_segment_evidence(
            mode_context(request, req.mode).bundle,
            weather,
            seg_id=req.seg_id,
            t=req.t,
            cond=req.cond,
            mode=req.mode,
            model_version=bundle.model_version,
        )
    result = await service.explain(resolved.cache_key, resolved.evidence)
    return ExplainData(text=result.text, source=result.source)


@extras.post("/explain", response_model=Envelope[ExplainData])
async def explain(
    req: ExplainRequest, request: Request, bundle: BundleDep, weather: WeatherDep
) -> Envelope[ExplainData]:
    return ok(await _explanation(req, request, bundle, weather), bundle.model_version)


def _audio(audio: bytes | None) -> Response:
    """MP3 from the voice chain, or 503 so the browser speaks with its device voice."""
    if audio is None:
        raise AppError("TTS_UNAVAILABLE", "Voice is unavailable; using the device voice.", 503)
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@extras.post("/tts", response_class=Response)
async def tts(
    req: ExplainRequest, request: Request, bundle: BundleDep, weather: WeatherDep
) -> Response:
    """Speak an explanation the server itself produced; clients cannot supply text."""
    text = (await _explanation(req, request, bundle, weather)).text
    service: VoiceChain = request.app.state.tts
    return _audio(await service.speak(text))


MAX_ALERT_INDEX = 999


class AlertSpeechRequest(BaseModel):
    """Which alert to speak; the words always come from the cached route, never the client."""

    model_config = ConfigDict(extra="forbid")

    route_key: str = Field(pattern=r"^[0-9a-f]{16}$")
    index: int = Field(ge=0, le=MAX_ALERT_INDEX)
    kind: AlertKind = "pp"


@extras.post("/tts/alert", response_class=Response)
async def tts_alert(req: AlertSpeechRequest, request: Request) -> Response:
    """A navigation alert ("High traffic risk ahead. <street>.") in the server voice."""
    text = resolve_alert_text(_routes_cache(request), req.route_key, req.kind, req.index)
    voices: AlertAudio = request.app.state.alert_audio
    return _audio(await voices.speak(req.route_key, req.kind, req.index, text))


@extras.get("/conditions/live", response_model=Envelope[ConditionUsed])
async def live_conditions(bundle: BundleDep, weather: WeatherDep) -> Envelope[ConditionUsed]:
    resolved = await weather.resolve("live", now_atlanta())
    data = ConditionUsed(
        cond="wet" if resolved.wet else "dry",
        source=resolved.source,  # type: ignore[arg-type]
        label=resolved.label,
    )
    return ok(data, bundle.model_version)


@extras.get("/geocode", response_model=Envelope[list[GeoResultOut]])
async def geocode(
    request: Request,
    bundle: BundleDep,
    q: Annotated[str, Query(min_length=1, max_length=80)],
) -> Envelope[list[GeoResultOut]]:
    service: GeocodeService = request.app.state.geocoder
    west, south, east, north = bundle.manifest["coverage_bbox"]
    results = [
        GeoResultOut(
            label=r.label,
            address=r.address,
            lat=r.lat,
            lon=r.lon,
            in_coverage=west <= r.lon <= east and south <= r.lat <= north,
        )
        for r in await service.search(q)
    ]
    return ok(results, bundle.model_version)


class HourlyOut(BaseModel):
    seg_id: int
    crashes: list[float]
    ped_crashes: list[float]
    source: Literal["tiger_data"]


@extras.get("/segments/{seg_id}/hourly", response_model=Envelope[HourlyOut])
async def segment_hourly(
    seg_id: int, request: Request, bundle: BundleDep, mode: ModeKey = "walk"
) -> Envelope[HourlyOut]:
    """When crashes happened on this street, by hour (Tiger Data continuous aggregate).

    Walk segments only: the hourly history is keyed by walk segment ids.
    """
    if mode != "walk" or not 0 <= seg_id < bundle.n_segments:
        raise AppError("NOT_FOUND", "That street segment is not in PathPro coverage.", 404)
    history: HistoryRepository = request.app.state.history
    profile = await history.hourly(seg_id)
    if profile is None:
        raise AppError(
            "HISTORY_UNAVAILABLE", "Crash history by hour is unavailable right now.", 503
        )
    data = HourlyOut(
        seg_id=seg_id,
        crashes=list(profile.crashes),
        ped_crashes=list(profile.ped_crashes),
        source="tiger_data",
    )
    return ok(data, bundle.model_version)
