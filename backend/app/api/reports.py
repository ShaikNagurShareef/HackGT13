"""Community street reports (MongoDB Atlas). Context for walkers; never an input to scores."""

from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_bundle
from app.api.envelope import AppError, Envelope, ok
from app.api.schemas import ReportOut, ReportRequest, ReportSummaryOut
from app.repositories.artifacts import Bundle
from app.repositories.reports import ReportsRepository
from app.services.reports import (
    report_out,
    segment_location,
    submit_report,
    summary_out,
    unavailable,
)

reports = APIRouter()
BundleDep = Annotated[Bundle, Depends(get_bundle)]
MAX_BBOX_SPAN_DEG = 0.3  # a city viewport; wider requests are refused, not truncated
BBOX_PARTS = 4


def get_reports(request: Request) -> ReportsRepository:
    repo: ReportsRepository = request.app.state.reports
    if not repo.configured:
        raise unavailable()
    return repo


ReportsDep = Annotated[ReportsRepository, Depends(get_reports)]


def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """minLon,minLat,maxLon,maxLat -> validated floats, or a BAD_BBOX error."""
    bad = AppError("BAD_BBOX", "Map area must be minLon,minLat,maxLon,maxLat within 0.3°.", 422)
    parts = raw.split(",")
    if len(parts) != BBOX_PARTS:
        raise bad
    try:
        w, s, e, n = (float(p) for p in parts)
    except ValueError as exc:
        raise bad from exc
    finite = all(math.isfinite(v) for v in (w, s, e, n))
    in_range = finite and -180 <= w < e <= 180 and -90 <= s < n <= 90
    if not in_range or e - w > MAX_BBOX_SPAN_DEG or n - s > MAX_BBOX_SPAN_DEG:
        raise bad
    return w, s, e, n


@reports.post("/reports", response_model=Envelope[ReportOut])
async def create_report(
    req: ReportRequest, repo: ReportsDep, bundle: BundleDep
) -> Envelope[ReportOut]:
    """Flag a traffic-related street issue; a repeat report confirms it for another 14 days."""
    saved = await submit_report(repo, bundle, req.seg_id, req.category)
    return ok(saved, bundle.model_version)


@reports.get("/reports", response_model=Envelope[list[ReportOut]])
async def reports_in_view(
    repo: ReportsDep,
    bundle: BundleDep,
    bbox: Annotated[str, Query(max_length=120)],
) -> Envelope[list[ReportOut]]:
    found = await repo.in_bbox(*parse_bbox(bbox))
    if found is None:
        raise unavailable()
    return ok([report_out(r) for r in found], bundle.model_version)


@reports.get("/reports/summary", response_model=Envelope[list[ReportSummaryOut]])
async def reports_summary(repo: ReportsDep, bundle: BundleDep) -> Envelope[list[ReportSummaryOut]]:
    rows = await repo.summary()
    if rows is None:
        raise unavailable()
    return ok([summary_out(r) for r in rows], bundle.model_version)


@reports.get("/segments/{seg_id}/reports", response_model=Envelope[list[ReportOut]])
async def segment_reports(
    seg_id: int, repo: ReportsDep, bundle: BundleDep
) -> Envelope[list[ReportOut]]:
    segment_location(bundle, seg_id)  # 404 for segments outside coverage
    found = await repo.for_segments([seg_id])
    if found is None:
        raise unavailable()
    return ok([report_out(r) for r in found], bundle.model_version)
