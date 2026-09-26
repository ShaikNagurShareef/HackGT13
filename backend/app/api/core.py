"""Core endpoints: health, meta, routes, and segment detail."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_bundle, get_router, get_weather
from app.api.envelope import AppError, Envelope, ok
from app.api.schemas import (
    Condition,
    FactorOut,
    HealthData,
    MetaData,
    RouteRequest,
    RoutesData,
    SegmentDetail,
)
from app.domain.router import Router
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
    )
    return ok(data, bundle.model_version)


@api.get("/meta", response_model=Envelope[MetaData])
async def meta(bundle: BundleDep) -> Envelope[MetaData]:
    m = bundle.manifest
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
    )
    return ok(data, bundle.model_version)


@api.post("/routes", response_model=Envelope[RoutesData])
async def routes(
    req: RouteRequest,
    request: Request,
    bundle: BundleDep,
    router: Annotated[Router, Depends(get_router)],
    weather: Annotated[WeatherService, Depends(get_weather)],
) -> Envelope[RoutesData]:
    planned = await plan_routes(bundle, router, weather, req, request.app.state.hexes)
    # Community reports are display-only context; the explanation evidence ignores them.
    reports = await route_reports(request.app.state.reports, planned)
    data = planned.model_copy(update={"reports": reports})
    request.app.state.routes_cache[data.route_key] = data  # evidence for /explain stays server-side
    return ok(data, bundle.model_version)


@api.get("/segments/{seg_id}", response_model=Envelope[SegmentDetail])
async def segment(
    seg_id: int,
    bundle: BundleDep,
    weather: Annotated[WeatherService, Depends(get_weather)],
    t: Annotated[str, Query(max_length=40)] = "now",
    cond: Condition = "live",
) -> Envelope[SegmentDetail]:
    try:
        at = parse_departure(t)
    except ValueError as exc:
        raise AppError("BAD_TIME", "Pick a valid time.", status=422) from exc
    resolved = await weather.resolve(cond, at)
    return ok(segment_detail(bundle, seg_id, at, resolved), bundle.model_version)
