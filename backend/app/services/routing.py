"""Route requests: coverage checks, snapping, condition resolution, and user-facing copy.

Ride modes (bike / e-bike / scooter) plan on the ride model at the mode's speed; the
lit-and-busy preference and the personal-safety summary are walk-only.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

from app.api.envelope import AppError
from app.api.schemas import (
    AlertOut,
    ConditionUsed,
    NamedSegmentOut,
    RouteOut,
    RouteRequest,
    RoutesData,
)
from app.domain.alerts import avoided_segments, walk_alerts
from app.domain.modes import TravelMode, mode_for
from app.domain.route_metrics import RouteMetrics
from app.domain.router import DEFAULT_PREFERENCE, RoutePlan, Router, RoutingError
from app.domain.scoring import band_for
from app.domain.timeutil import parse_departure
from app.repositories.artifacts import Bundle
from app.repositories.hexes import HexBundle
from app.repositories.safety import SafetyBundle
from app.services.safety import route_safety
from app.services.weather import WeatherService

SNAP_LIMIT_M = 150.0


def _in_bbox(bbox: list[float], lat: float, lon: float) -> bool:
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def in_coverage(bundle: Bundle, hexes: HexBundle | None, lat: float, lon: float) -> bool:
    """City hexes when available (follows the real city line), else the bounding box."""
    if hexes is not None:
        return hexes.cell_for(lat, lon) is not None
    return _in_bbox(bundle.manifest["coverage_bbox"], lat, lon)


def _check_coverage(bundle: Bundle, req: RouteRequest, hexes: HexBundle | None) -> None:
    for point in (req.origin, req.destination):
        if not in_coverage(bundle, hexes, point.lat, point.lon):
            raise AppError(
                "OUT_OF_COVERAGE",
                "PathPro covers the City of Atlanta for now. "
                "Pick a starting point and destination inside city limits.",
                status=422,
            )


def _snap(router: Router, lat: float, lon: float, mode: TravelMode) -> tuple[int, float]:
    node, dist = router.snap(lon, lat)
    if dist > SNAP_LIMIT_M:
        target = "street or bike path" if mode.is_ride else "sidewalk or street"
        raise AppError("SNAP_TOO_FAR", f"Move the pin closer to a {target}.", status=422)
    return node, dist


def route_out(
    bundle: Bundle,
    r: RouteMetrics,
    safety: SafetyBundle | None = None,
    depart: datetime | None = None,
) -> RouteOut:
    alerts = [
        AlertOut(
            start_m=round(a.start_m),
            end_m=round(a.end_m),
            names=list(a.names),
            score=a.score,
            stretches=a.stretches,
        )
        for a in walk_alerts(r.edges, bundle.seg_meta["name"])
    ]
    return RouteOut(
        alerts=alerts,
        coords=[[round(x, 6), round(y, 6)] for x, y in r.coords],
        duration_s=round(r.duration_s, 1),
        distance_m=round(r.distance_m, 1),
        risk_score=r.risk_score,
        band=band_for(r.risk_score).value,
        exposure=round(r.exposure, 4),
        high_risk_m=round(r.high_risk_m),
        limited_data_m=round(r.limited_data_m),
        segment_ids=sorted({s.seg_id for s in r.edges if s.seg_id >= 0}),
        top_segments=[
            NamedSegmentOut(seg_id=s.seg_id, name=s.name, score=s.score) for s in r.top_segments
        ],
        safety=route_safety(safety, r, depart) if safety and depart else None,
    )


def _message(plan: RoutePlan, mode: TravelMode) -> str | None:
    if plan.message_code == "fastest_is_lower_risk":
        return "The fastest route is already the lower-risk option."
    if plan.message_code == "long_trip":
        trip = "ride" if mode.is_ride else "walk"
        return f"This is a long {trip}. Consider MARTA for part of it."
    if plan.message_code == "tradeoff_exists" and plan.tradeoff_extra_s is not None:
        extra = round(plan.tradeoff_extra_s / 60)
        return (
            f"A lower-risk route exists but adds {extra} min. "
            "Showing the best option under 6 extra min."
        )
    if plan.pathpro and plan.pathpro.limited_data_m > 0:
        return "Part of this route has limited crash history; score is less certain."
    return None


def _route_key(req: RouteRequest, depart: datetime, cond: str, prefer: str) -> str:
    o, d = req.origin, req.destination
    raw = f"{o.lat:.5f},{o.lon:.5f}|{d.lat:.5f},{d.lon:.5f}|{depart:%Y-%m-%dT%H}|{cond}"
    if prefer != DEFAULT_PREFERENCE:
        raw += f"|{prefer}"  # default keys are unchanged
    if req.mode != "walk":
        raw += f"|mode={req.mode}"  # walk keys are unchanged
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _avoided(
    bundle: Bundle, fastest: RouteMetrics, pp: RouteMetrics | None
) -> list[NamedSegmentOut]:
    if pp is None:
        return []
    scores = {s.seg_id: round(s.score) for s in fastest.edges}
    names = bundle.seg_meta["name"]
    return [
        NamedSegmentOut(seg_id=i, name=names[i], score=scores[i])
        for i in avoided_segments(fastest.edges, pp.edges, names)
    ]


def _no_route_message(exc: RoutingError, mode: TravelMode) -> str:
    if exc.code == "NO_CONNECTION":
        kind = "rideable" if mode.is_ride else "walkable"
        return f"No {kind} connection found between these points."
    return str(exc)


async def plan_routes(
    bundle: Bundle,
    router: Router,
    weather: WeatherService,
    req: RouteRequest,
    hexes: HexBundle | None = None,
    safety: SafetyBundle | None = None,
) -> RoutesData:
    try:
        depart = parse_departure(req.depart_at)
    except ValueError as exc:
        raise AppError("BAD_DEPARTURE", "Pick a valid departure time.", status=422) from exc
    mode = mode_for(req.mode)
    prefer = DEFAULT_PREFERENCE if mode.is_ride else req.prefer
    safety = None if mode.is_ride else safety
    _check_coverage(bundle, req, hexes)
    origin, _ = _snap(router, req.origin.lat, req.origin.lon, mode)
    dest, _ = _snap(router, req.destination.lat, req.destination.lon, mode)
    resolved = await weather.resolve(req.cond, depart)
    try:
        # ~120 ms of CPU: keep the event loop free for other requests and LLM calls.
        plan = await asyncio.to_thread(
            router.plan, origin, dest, depart, resolved.wet, prefer, mode.profile
        )
    except RoutingError as exc:
        raise AppError(exc.code, _no_route_message(exc, mode), status=422) from exc
    fastest, pp = plan.fastest, plan.pathpro
    reduction = (
        round((1 - pp.exposure / fastest.exposure) * 100) if pp and fastest.exposure else None
    )
    if reduction is not None and reduction <= 0:
        reduction = None  # a lit-and-busy pick may not cut traffic exposure; never show < 0
    cond = "wet" if resolved.wet else "dry"
    return RoutesData(
        avoided=_avoided(bundle, fastest, pp),
        condition_used=ConditionUsed(cond=cond, source=resolved.source, label=resolved.label),  # type: ignore[arg-type]
        depart_at=depart.isoformat(),
        fastest=route_out(bundle, fastest, safety, depart),
        pathpro=route_out(bundle, pp, safety, depart) if pp else None,
        message_code=plan.message_code,
        message=_message(plan, mode),
        time_cost_min=round((pp.duration_s - fastest.duration_s) / 60, 1) if pp else None,
        exposure_reduction_pct=reduction,
        unavoidable=list(plan.unavoidable),
        route_key=_route_key(req, depart, cond, prefer),
        mode=req.mode,
        prefer=prefer,  # type: ignore[arg-type]
    )
