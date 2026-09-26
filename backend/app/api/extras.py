"""Explanations, live conditions, and geocoding endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import get_bundle, get_weather
from app.api.envelope import AppError, Envelope, ok
from app.api.schemas import Condition, ConditionUsed, RoutesData
from app.domain.timeutil import cell_at, now_atlanta, parse_departure
from app.repositories.artifacts import Bundle
from app.repositories.history import HistoryRepository
from app.services.explain.evidence import route_evidence, segment_evidence
from app.services.explain.service import ExplainService
from app.services.geocode import GeocodeService
from app.services.segments import segment_detail
from app.services.tts import TtsService
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
        routes = _routes_cache(request).get(req.route_key or "")
        if routes is None:
            raise AppError("ROUTE_EXPIRED", "Route details expired. Request the route again.", 404)
        key = f"route:{req.route_key}:{bundle.model_version}"
        result = await service.explain(key, route_evidence(routes))
        return ExplainData(text=result.text, source=result.source)
    if req.seg_id is None:
        raise AppError("BAD_REQUEST", "seg_id is required for segment explanations.", 422)
    try:
        at = parse_departure(req.t)
    except ValueError as exc:
        raise AppError("BAD_TIME", "Pick a valid time.", 422) from exc
    resolved = await weather.resolve(req.cond, at)
    detail = segment_detail(bundle, req.seg_id, at, resolved)
    cell = cell_at(at, resolved.wet)
    key = f"seg:{req.seg_id}:{'|'.join(map(str, cell.key))}:{bundle.model_version}"
    result = await service.explain(key, segment_evidence(detail))
    return ExplainData(text=result.text, source=result.source)


@extras.post("/explain", response_model=Envelope[ExplainData])
async def explain(
    req: ExplainRequest, request: Request, bundle: BundleDep, weather: WeatherDep
) -> Envelope[ExplainData]:
    return ok(await _explanation(req, request, bundle, weather), bundle.model_version)


@extras.post("/tts", response_class=Response)
async def tts(
    req: ExplainRequest, request: Request, bundle: BundleDep, weather: WeatherDep
) -> Response:
    """Speak an explanation the server itself produced; clients cannot supply text."""
    text = (await _explanation(req, request, bundle, weather)).text
    service: TtsService = request.app.state.tts
    audio = await service.speak(text)
    if audio is None:
        raise AppError("TTS_UNAVAILABLE", "Voice is unavailable; using the device voice.", 503)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


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
async def segment_hourly(seg_id: int, request: Request, bundle: BundleDep) -> Envelope[HourlyOut]:
    """When crashes happened on this street, by hour (Tiger Data continuous aggregate)."""
    if not 0 <= seg_id < bundle.n_segments:
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
