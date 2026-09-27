"""Server-side evidence resolution shared by /explain, /tts and Ask PathPro.

Clients only name what they are looking at (a segment id, a cached route key, an area cell);
the evidence itself is always rebuilt here from the model, never taken from the request.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.api.envelope import AppError
from app.api.schemas import RoutesData
from app.domain.modes import ModeKey
from app.domain.timeutil import cell_at
from app.repositories.artifacts import Bundle
from app.repositories.hexes import HexBundle
from app.services.areas import parse_time, resolve_area_detail
from app.services.explain.evidence import (
    Evidence,
    area_evidence,
    conditions_evidence,
    route_evidence,
    segment_evidence,
)
from app.services.segments import segment_detail
from app.services.weather import WeatherService

WALK = "walk"


@dataclass(frozen=True)
class ResolvedEvidence:
    cache_key: str  # the explanation cache key for this evidence
    evidence: Evidence


def resolve_route_evidence(
    cache: Mapping[str, RoutesData], route_key: str | None, model_version: str
) -> ResolvedEvidence:
    """A route's evidence from the routes cache; ROUTE_EXPIRED when it has been evicted."""
    routes = cache.get(route_key or "")
    if routes is None:
        raise AppError("ROUTE_EXPIRED", "Route details expired. Request the route again.", 404)
    return ResolvedEvidence(f"route:{route_key}:{model_version}", route_evidence(routes))


async def resolve_segment_evidence(
    model: Bundle,
    weather: WeatherService,
    *,
    seg_id: int,
    t: str,
    cond: str,
    mode: ModeKey,
    model_version: str,
) -> ResolvedEvidence:
    """A street segment's evidence at a time and condition, on the given mode's model."""
    at = parse_time(t)
    resolved = await weather.resolve(cond, at)
    detail = segment_detail(model, seg_id, at, resolved, mode)
    cell = cell_at(at, resolved.wet)
    key = f"seg:{seg_id}:{'|'.join(map(str, cell.key))}:{model_version}"
    if mode != WALK:
        key += f":{mode}"  # walk cache keys are unchanged
    return ResolvedEvidence(key, segment_evidence(detail))


async def resolve_area_evidence(
    hexes: HexBundle | None,
    bundle: Bundle,
    weather: WeatherService,
    cell: str,
    t: str,
    cond: str,
) -> Evidence:
    return area_evidence(await resolve_area_detail(hexes, bundle, weather, cell, t, cond))


async def resolve_conditions_evidence(weather: WeatherService, t: str, cond: str) -> Evidence:
    at = parse_time(t)
    return conditions_evidence(await weather.resolve(cond, at), at)
