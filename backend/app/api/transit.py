"""Transit hand-off: MARTA rail stations inside PathPro coverage."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_bundle
from app.api.envelope import Envelope, ok
from app.api.schemas import StationOut
from app.domain.transit import load_rail_stations, stations_in_bbox
from app.repositories.artifacts import Bundle

transit = APIRouter()
BundleDep = Annotated[Bundle, Depends(get_bundle)]


@transit.get("/transit/stations", response_model=Envelope[list[StationOut]])
async def rail_stations(bundle: BundleDep) -> Envelope[list[StationOut]]:
    inside = stations_in_bbox(load_rail_stations(), list(bundle.manifest["coverage_bbox"]))
    data = [StationOut(name=s.name, lat=s.lat, lon=s.lon, lines=list(s.lines)) for s in inside]
    return ok(data, bundle.model_version)
