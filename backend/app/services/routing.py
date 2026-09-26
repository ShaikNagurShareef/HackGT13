"""Route requests: coverage checks, snapping, condition resolution, and user-facing copy."""

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
from app.domain.route_metrics import RouteMetrics
from app.domain.router import RoutePlan, Router, RoutingError
from app.domain.scoring import band_for
from app.domain.timeutil import parse_departure
from app.repositories.artifacts import Bundle
from app.services.weather import WeatherService

SNAP_LIMIT_M = 150.0


def _in_bbox(bbox: list[float], lat: float, lon: float) -> bool:
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def _check_coverage(bundle: Bundle, req: RouteRequest) -> None:
    bbox = bundle.manifest["coverage_bbox"]
    for point in (req.origin, req.destination):
        if not _in_bbox(bbox, point.lat, point.lon):
            raise AppError(
                "OUT_OF_COVERAGE",
                "PathPulse covers Midtown, Georgia Tech, and Downtown for now. "
                "Route to the edge of coverage?",
                status=422,
            )


def _snap(router: Router, lat: float, lon: float) -> tuple[int, float]:
    node, dist = router.snap(lon, lat)
    if dist > SNAP_LIMIT_M:
        raise AppError("SNAP_TOO_FAR", "Move the pin closer to a sidewalk or street.", status=422)
    return node, dist


def route_out(bundle: Bundle, r: RouteMetrics) -> RouteOut:
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
    )


def _message(plan: RoutePlan) -> str | None:
    if plan.message_code == "fastest_is_lower_risk":
        return "The fastest route is already the lower-risk option."
    if plan.message_code == "long_trip":
        return "This is a long walk. Consider MARTA for part of it."
    if plan.message_code == "tradeoff_exists" and plan.tradeoff_extra_s is not None:
        extra = round(plan.tradeoff_extra_s / 60)
        return (
            f"A lower-risk route exists but adds {extra} min. "
            "Showing the best option under 6 extra min."
        )
    if plan.pathpulse and plan.pathpulse.limited_data_m > 0:
        return "Part of this route has limited crash history; score is less certain."
    return None


def _route_key(req: RouteRequest, depart: datetime, cond: str) -> str:
    o, d = req.origin, req.destination
    raw = f"{o.lat:.5f},{o.lon:.5f}|{d.lat:.5f},{d.lon:.5f}|{depart:%Y-%m-%dT%H}|{cond}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def plan_routes(
    bundle: Bundle, router: Router, weather: WeatherService, req: RouteRequest
) -> RoutesData:
    try:
        depart = parse_departure(req.depart_at)
    except ValueError as exc:
        raise AppError("BAD_DEPARTURE", "Pick a valid departure time.", status=422) from exc
    _check_coverage(bundle, req)
    origin, _ = _snap(router, req.origin.lat, req.origin.lon)
    dest, _ = _snap(router, req.destination.lat, req.destination.lon)
    resolved = await weather.resolve(req.cond, depart)
    try:
        # ~120 ms of CPU: keep the event loop free for other requests and LLM calls.
        plan = await asyncio.to_thread(router.plan, origin, dest, depart, resolved.wet)
    except RoutingError as exc:
        raise AppError(exc.code, str(exc), status=422) from exc
    fastest, pp = plan.fastest, plan.pathpulse
    reduction = (
        round((1 - pp.exposure / fastest.exposure) * 100) if pp and fastest.exposure else None
    )
    cond = "wet" if resolved.wet else "dry"
    avoided = []
    if pp is not None:
        scores = {s.seg_id: round(s.score) for s in fastest.edges}
        avoided = [
            NamedSegmentOut(seg_id=i, name=bundle.seg_meta["name"][i], score=scores[i])
            for i in avoided_segments(fastest.edges, pp.edges, bundle.seg_meta["name"])
        ]
    return RoutesData(
        avoided=avoided,
        condition_used=ConditionUsed(cond=cond, source=resolved.source, label=resolved.label),  # type: ignore[arg-type]
        depart_at=depart.isoformat(),
        fastest=route_out(bundle, fastest),
        pathpulse=route_out(bundle, pp) if pp else None,
        message_code=plan.message_code,
        message=_message(plan),
        time_cost_min=round((pp.duration_s - fastest.duration_s) / 60, 1) if pp else None,
        exposure_reduction_pct=reduction,
        unavoidable=list(plan.unavoidable),
        route_key=_route_key(req, depart, cond),
    )
