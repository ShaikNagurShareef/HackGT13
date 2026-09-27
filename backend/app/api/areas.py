"""City Pulse endpoints: citywide area traffic-risk scores (CITY-01..04)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app.api.deps import get_bundle, get_weather
from app.api.envelope import Envelope, ok
from app.api.schemas import Condition
from app.repositories.artifacts import Bundle
from app.repositories.hexes import HexBundle
from app.services.areas import AreaDetail, area_detail, require_hexes, resolve_area_detail
from app.services.weather import WeatherService

areas = APIRouter()
__all__ = ["AreaDetail", "area_detail", "areas"]


def _hexes(request: Request) -> HexBundle:
    return require_hexes(request.app.state.hexes)


async def _respond(
    request: Request, bundle: Bundle, weather: WeatherService, cell: str | None, t: str, cond: str
) -> Envelope[AreaDetail]:
    hexes = _hexes(request)
    detail = await resolve_area_detail(hexes, bundle, weather, cell, t, cond)
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
