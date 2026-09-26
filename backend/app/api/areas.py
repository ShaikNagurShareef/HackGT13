"""City Pulse endpoints: citywide area traffic-risk scores (CITY-01..04)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel

from app.api.deps import get_bundle, get_weather
from app.api.envelope import AppError, Envelope, ok
from app.api.schemas import Condition, ConditionUsed, FactorOut
from app.domain.scoring import attribute, band_for
from app.domain.timeutil import cell_at, parse_departure
from app.repositories.artifacts import Bundle
from app.repositories.hexes import HexBundle
from app.services.weather import WeatherService

areas = APIRouter()
TOP_FACTORS = 4


class AreaDetail(BaseModel):
    cell: str
    lat: float
    lon: float
    score: int
    band: str
    confidence: Literal["high", "medium", "limited"]
    baseline_points: int
    factors: list[FactorOut]
    remainder_points: int
    crashes: float
    ped_crashes: float
    period: str
    in_street_coverage: bool
    condition_used: ConditionUsed
    at: str


def _hexes(request: Request) -> HexBundle:
    hexes: HexBundle | None = request.app.state.hexes
    if hexes is None:
        raise AppError("CITY_PULSE_UNAVAILABLE", "Citywide area scores are not available.", 503)
    return hexes


def area_detail(
    hexes: HexBundle, bundle: Bundle, cell: str, at: datetime, wet: bool, used: ConditionUsed
) -> AreaDetail:
    i = hexes.index[cell]
    factors = {k: float(v) for k, v in zip(hexes.factor_keys, hexes.factors[i], strict=True)}
    factors[hexes.temporal_key] = hexes.temporal_log(i, cell_at(at, wet))
    result = attribute(hexes.base, factors, hexes.quantiles, top_n=TOP_FACTORS)
    lat, lon = float(hexes.lat[i]), float(hexes.lon[i])
    west, south, east, north = bundle.manifest["coverage_bbox"]
    return AreaDetail(
        cell=cell,
        lat=lat,
        lon=lon,
        score=result.score,
        band=band_for(result.score).value,
        confidence=hexes.confidence[i],  # type: ignore[arg-type]
        baseline_points=result.baseline_points,
        factors=[
            FactorOut(key=f.key, label=hexes.labels[f.key], points=f.points) for f in result.factors
        ],
        remainder_points=result.remainder_points,
        crashes=float(hexes.crashes[i]),
        ped_crashes=float(hexes.ped_crashes[i]),
        period="2020-2024",
        in_street_coverage=west <= lon <= east and south <= lat <= north,
        condition_used=used,
        at=at.isoformat(),
    )


async def _respond(
    request: Request, bundle: Bundle, weather: WeatherService, cell: str | None, t: str, cond: str
) -> Envelope[AreaDetail]:
    hexes = _hexes(request)
    if cell is None or cell not in hexes.index:
        raise AppError("OUTSIDE_CITY", "City Pulse covers the City of Atlanta.", 404)
    try:
        at = parse_departure(t)
    except ValueError as exc:
        raise AppError("BAD_TIME", "Pick a valid time.", 422) from exc
    resolved = await weather.resolve(cond, at)
    used = ConditionUsed(
        cond="wet" if resolved.wet else "dry",
        source=resolved.source,  # type: ignore[arg-type]
        label=resolved.label,
    )
    detail = area_detail(hexes, bundle, cell, at, resolved.wet, used)
    return ok(detail, bundle.model_version)


BundleDep = Annotated[Bundle, Depends(get_bundle)]
WeatherDep = Annotated[WeatherService, Depends(get_weather)]
TimeQ = Annotated[str, Query(max_length=40)]


@areas.get("/areas/lookup", response_model=Envelope[AreaDetail])
async def area_lookup(
    request: Request,
    bundle: BundleDep,
    weather: WeatherDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    t: TimeQ = "now",
    cond: Condition = "live",
) -> Envelope[AreaDetail]:
    cell = _hexes(request).cell_for(lat, lon)
    return await _respond(request, bundle, weather, cell, t, cond)


@areas.get("/areas/{cell}", response_model=Envelope[AreaDetail])
async def area(
    cell: Annotated[str, Path(pattern=r"^[0-9a-f]{15}$")],
    request: Request,
    bundle: BundleDep,
    weather: WeatherDep,
    t: TimeQ = "now",
    cond: Condition = "live",
) -> Envelope[AreaDetail]:
    return await _respond(request, bundle, weather, cell, t, cond)
