"""Core endpoints: health, meta, routes, and segment detail."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_bundle, get_weather, mode_context, ride_available
from app.api.envelope import AppError, Envelope, ok
from app.api.schemas import (
    Condition,
    FactorOut,
    HealthData,
    MetaData,
    ModeOut,
    ModesHealth,
    RouteRequest,
    RoutesData,
    SegmentDetail,
)
from app.domain.modes import MODES, ModeKey
from app.domain.timeutil import parse_departure
from app.repositories.artifacts import Bundle
from app.services.reports import route_reports
from app.services.routing import plan_routes
from app.services.segments import segment_detail
from app.services.weather import WeatherService

api = APIRouter()
BundleDep = Annotated[Bundle, Depends(get_bundle)]


@api.get("/healthz", response_model=Envelope[HealthData])
async def healthz(request: Request, bundle: BundleDep) -> Envelope[HealthData]:
    database = await request.app.state.history.ping()
    reports = await request.app.state.reports.ping()
    data = HealthData(
        status="degraded" if "unavailable" in (database, reports) else "ok",
        model_version=bundle.model_version,
        segments=bundle.n_segments,
        graph_nodes=len(bundle.graph.node_lon),
        database=database,
        reports=reports,
        safety="ok" if getattr(request.app.state, "safety", None) is not None else "unavailable",
        modes=ModesHealth(ride="ok" if ride_available(request) else "unavailable"),
    )
    return ok(data, bundle.model_version)


def _modes(ride: Bundle | None) -> list[ModeOut]:
    return [
        ModeOut(
            key=mode.key,
            label=mode.label,
            available=ride is not None or not mode.is_ride,
            speed_kmh=round(mode.speed_kmh, 2),
            network=mode.network,
            static_prefix=mode.static_prefix,  # type: ignore[arg-type]
        )
        for mode in MODES.values()
    ]


@api.get("/meta", response_model=Envelope[MetaData])
async def meta(request: Request, bundle: BundleDep) -> Envelope[MetaData]:
    m = bundle.manifest
    ride: Bundle | None = getattr(request.app.state, "ride_bundle", None)
    data = MetaData(
        model_version=bundle.model_version,
        data_through=m["data_through"],
        n_segments=bundle.n_segments,
        coverage_bbox=list(m["coverage_bbox"]),
        day_groups=list(m["day_groups"]),
        conditions=list(m["conditions"]),
        reference_dates=dict(m.get("reference_dates", {})),
        frame_light=dict(m.get("frame_light", {})),
        static_base=f"/static/{bundle.model_version}",
        headline=dict(bundle.metrics.get("headline", {})),
        spatial_factors=[
            FactorOut(key=k, label=v, points=0) for k, v in bundle.spatial_labels.items()
        ],
        temporal_factors=[
            FactorOut(key=k, label=v, points=0) for k, v in bundle.temporal_labels.items()
        ],
        modes=_modes(ride),
        ride_model=dict(ride.metrics.get("headline", {})) if ride is not None else None,
    )
    return ok(data, bundle.model_version)


@api.post("/routes", response_model=Envelope[RoutesData])
async def routes(
    req: RouteRequest,
    request: Request,
    weather: Annotated[WeatherService, Depends(get_weather)],
) -> Envelope[RoutesData]:
    ctx = mode_context(request, req.mode)
    bundle = ctx.bundle
    planned = await plan_routes(
        bundle, ctx.router, weather, req, request.app.state.hexes, request.app.state.safety
    )
    # Community reports are display-only context on walk segments; evidence ignores them.
    reports = [] if ctx.mode.is_ride else await route_reports(request.app.state.reports, planned)
    data = planned.model_copy(update={"reports": reports})
    request.app.state.routes_cache[data.route_key] = data  # evidence for /explain stays server-side
    return ok(data, bundle.model_version)


@api.get("/segments/{seg_id}", response_model=Envelope[SegmentDetail])
async def segment(
    seg_id: int,
    request: Request,
    weather: Annotated[WeatherService, Depends(get_weather)],
    t: Annotated[str, Query(max_length=40)] = "now",
    cond: Condition = "live",
    mode: ModeKey = "walk",
) -> Envelope[SegmentDetail]:
    bundle = mode_context(request, mode).bundle  # ride segment ids index the ride model
    try:
        at = parse_departure(t)
    except ValueError as exc:
        raise AppError("BAD_TIME", "Pick a valid time.", status=422) from exc
    resolved = await weather.resolve(cond, at)
    return ok(segment_detail(bundle, seg_id, at, resolved, mode), bundle.model_version)
