"""Personal-safety layer: signals (lighting, foot traffic, help points) and an informational
view of reported crimes against persons, aggregated to H3 hexes by day part.

Crime data never reaches routing or the traffic-risk model; see services/safety.py.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.deps import get_bundle
from app.api.envelope import AppError, Envelope, ok
from app.api.reports import parse_bbox
from app.domain.timeutil import now_atlanta
from app.repositories.artifacts import Bundle
from app.repositories.safety import SafetyBundle
from app.services.safety import help_points_in_bbox, hexes_in_bbox

safety = APIRouter()


class SourceOut(BaseModel):
    name: str
    url: str
    license: str


class DayPartOut(BaseModel):
    key: str
    label: str
    hours: list[int]


class SafetyMetaOut(BaseModel):
    data_through: str
    sources: list[SourceOut]
    crime_categories: list[str]
    day_parts: list[DayPartOut]


class SafetyHexOut(BaseModel):
    h3: str
    lat: float
    lon: float
    crimes_persons_12mo: int
    crime_band: Literal["lower", "typical", "higher"]
    lit_share: float | None
    activity_band: Literal["quiet", "moderate", "busy"] | None
    help_points: int


class HelpPointOut(BaseModel):
    kind: Literal["blue_light", "police", "fire", "hospital", "marta"]
    name: str
    lat: float
    lon: float


def get_safety(request: Request) -> SafetyBundle:
    layer: SafetyBundle | None = getattr(request.app.state, "safety", None)
    if layer is None:
        raise AppError(
            "SAFETY_UNAVAILABLE", "Lighting, foot traffic and help points are not available.", 503
        )
    return layer


SafetyDep = Annotated[SafetyBundle, Depends(get_safety)]
BundleDep = Annotated[Bundle, Depends(get_bundle)]
BBoxQ = Annotated[str, Query(max_length=120)]


@safety.get("/safety/meta", response_model=Envelope[SafetyMetaOut])
async def safety_meta(layer: SafetyDep, bundle: BundleDep) -> Envelope[SafetyMetaOut]:
    m = layer.meta
    data = SafetyMetaOut(
        data_through=layer.data_through,
        sources=[SourceOut(**s) for s in m["sources"]],
        crime_categories=list(m["crime_categories"]),
        day_parts=[DayPartOut(**p) for p in m["day_parts"]],
    )
    return ok(data, bundle.model_version)


@safety.get("/safety/hexes", response_model=Envelope[list[SafetyHexOut]])
async def safety_hexes(
    layer: SafetyDep,
    bundle: BundleDep,
    bbox: BBoxQ,
    hour: Annotated[int | None, Query(ge=0, le=23)] = None,
) -> Envelope[list[SafetyHexOut]]:
    """Hexes in view for the day part containing `hour` (Atlanta time; default now)."""
    box = parse_bbox(bbox)
    at_hour = now_atlanta().hour if hour is None else hour
    rows = [SafetyHexOut(**vars(r)) for r in hexes_in_bbox(layer, box, at_hour)]
    return ok(rows, bundle.model_version)


@safety.get("/safety/help-points", response_model=Envelope[list[HelpPointOut]])
async def safety_help_points(
    layer: SafetyDep, bundle: BundleDep, bbox: BBoxQ
) -> Envelope[list[HelpPointOut]]:
    rows = [HelpPointOut(**vars(p)) for p in help_points_in_bbox(layer, parse_bbox(bbox))]
    return ok(rows, bundle.model_version)
