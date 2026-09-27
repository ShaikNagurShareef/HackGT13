"""What an Ask PathPro question is about: a street, a route, a City Pulse area, or nothing.

The client only names the thing on screen (ids and keys, never free text or coordinates); the
evidence is rebuilt here from the model. Without context, or when the named thing cannot be
resolved (an expired route, an unknown street or cell), the question gets live conditions only
and the answer says the context was dropped; it is never an error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import mode_context
from app.api.envelope import AppError
from app.api.schemas import Condition, RoutesData
from app.domain.modes import ModeKey
from app.repositories.artifacts import Bundle
from app.services.explain.evidence import Evidence
from app.services.explain.resolve import (
    resolve_area_evidence,
    resolve_conditions_evidence,
    resolve_route_evidence,
    resolve_segment_evidence,
)
from app.services.weather import WeatherService

log = logging.getLogger(__name__)

NOW, LIVE = "now", "live"
MAX_TIME_CHARS = 40
ContextUsed = Literal["segment", "route", "area", "conditions"]


class SegmentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["segment"]
    seg_id: int = Field(ge=0)
    t: str = Field(default=NOW, max_length=MAX_TIME_CHARS)
    cond: Condition = "live"
    mode: ModeKey = "walk"


class RouteContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["route"]
    route_key: str = Field(pattern=r"^[0-9a-f]{16}$")


class AreaContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["area"]
    cell: str = Field(pattern=r"^[0-9a-f]{15}$")
    t: str = Field(default=NOW, max_length=MAX_TIME_CHARS)
    cond: Condition = "live"


AskContext = Annotated[SegmentContext | RouteContext | AreaContext, Field(discriminator="kind")]


@dataclass(frozen=True)
class ResolvedContext:
    evidence: Evidence
    used: ContextUsed
    dropped: bool


async def _evidence(request: Request, context: AskContext, weather: WeatherService) -> Evidence:
    bundle: Bundle = request.app.state.bundle
    if isinstance(context, RouteContext):
        cache: dict[str, RoutesData] = request.app.state.routes_cache
        return resolve_route_evidence(cache, context.route_key, bundle.model_version).evidence
    if isinstance(context, SegmentContext):
        resolved = await resolve_segment_evidence(
            mode_context(request, context.mode).bundle,
            weather,
            seg_id=context.seg_id,
            t=context.t,
            cond=context.cond,
            mode=context.mode,
            model_version=bundle.model_version,
        )
        return resolved.evidence
    return await resolve_area_evidence(
        request.app.state.hexes, bundle, weather, context.cell, context.t, context.cond
    )


async def _conditions(weather: WeatherService, context: AskContext | None) -> Evidence:
    """Live conditions at the context's time and condition when it names valid ones."""
    if isinstance(context, SegmentContext | AreaContext):
        try:
            return await resolve_conditions_evidence(weather, context.t, context.cond)
        except AppError:
            pass  # an unusable time: fall back to now
    return await resolve_conditions_evidence(weather, NOW, LIVE)


async def resolve_ask_context(request: Request, context: AskContext | None) -> ResolvedContext:
    weather: WeatherService = request.app.state.weather
    if context is None:
        return ResolvedContext(await _conditions(weather, None), "conditions", dropped=False)
    try:
        return ResolvedContext(await _evidence(request, context, weather), context.kind, False)
    except AppError as exc:
        log.info("ask context dropped: %s", exc.code)  # the code only, never ids or keys
    return ResolvedContext(await _conditions(weather, context), "conditions", dropped=True)
