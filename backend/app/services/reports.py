"""Community street reports: server-side location, response shaping, and route context.

Reports sit beside the model's output. They never change a score, a route choice, or the
evidence the explanation LLM sees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from app.api.envelope import AppError
from app.api.schemas import ReportOut, ReportSummaryOut, RoutesData
from app.domain.reports import CategoryCount, StreetReport
from app.repositories.artifacts import Bundle
from app.repositories.reports import ReportsRepository

ROUTE_REPORTS_BUDGET_S = 0.5  # routes never wait longer than this on Atlas
COORD_DECIMALS = 6


@dataclass(frozen=True)
class SegmentLocation:
    street: str
    lon: float
    lat: float


def unavailable() -> AppError:
    return AppError(
        "REPORTS_UNAVAILABLE",
        "Community reports are unavailable right now. Traffic-risk scores still work.",
        status=503,
    )


def polyline_midpoint(points: np.ndarray) -> tuple[float, float]:
    """Point halfway along a short lon/lat polyline (local equirectangular distances)."""
    if len(points) == 1:
        return float(points[0][0]), float(points[0][1])
    scale = math.cos(math.radians(float(points[0][1])))
    steps = np.hypot(np.diff(points[:, 0]) * scale, np.diff(points[:, 1]))
    total = float(steps.sum())
    if total == 0:
        return float(points[0][0]), float(points[0][1])
    cumulative = np.concatenate([[0.0], np.cumsum(steps)])
    i = int(np.searchsorted(cumulative, total / 2, side="right")) - 1
    i = min(i, len(steps) - 1)
    t = (total / 2 - cumulative[i]) / steps[i] if steps[i] else 0.0
    lon, lat = points[i] + t * (points[i + 1] - points[i])
    return float(lon), float(lat)


def segment_location(bundle: Bundle, seg_id: int) -> SegmentLocation:
    """Street name and midpoint from the bundle's walk graph; clients never supply a location."""
    missing = AppError("NOT_FOUND", "That street segment is not in PathPro coverage.", 404)
    if not 0 <= seg_id < bundle.n_segments:
        raise missing
    edges = np.flatnonzero(bundle.graph.edge_seg == seg_id)
    if edges.size == 0:
        raise missing
    lon, lat = polyline_midpoint(bundle.graph.edge_coords(int(edges[0])))
    return SegmentLocation(
        street=str(bundle.seg_meta["name"][seg_id]),
        lon=round(lon, COORD_DECIMALS),
        lat=round(lat, COORD_DECIMALS),
    )


def report_out(report: StreetReport) -> ReportOut:
    return ReportOut(
        seg_id=report.seg_id,
        category=report.category,  # type: ignore[arg-type]  # validated in parse_report
        label=report.label,
        street=report.street,
        lon=report.lon,
        lat=report.lat,
        confirmations=report.confirmations,
        updated_at=report.updated_at,
        expires_at=report.expires_at,
    )


def summary_out(row: CategoryCount) -> ReportSummaryOut:
    return ReportSummaryOut(
        category=row.category,  # type: ignore[arg-type]  # filtered in the repository
        label=row.label,
        reports=row.reports,
        confirmations=row.confirmations,
    )


async def submit_report(
    repo: ReportsRepository, bundle: Bundle, seg_id: int, category: str
) -> ReportOut:
    if not repo.configured:
        raise unavailable()
    where = segment_location(bundle, seg_id)
    now = datetime.now(UTC)
    saved = await repo.report(seg_id, category, where.street, where.lon, where.lat, now)
    if saved is None:
        raise unavailable()
    return report_out(saved)


async def route_reports(repo: ReportsRepository, routes: RoutesData) -> list[ReportOut]:
    """Reports on the recommended route (PathPro if present, else fastest); [] on any failure."""
    if not repo.configured:
        return []
    chosen = routes.pathpro or routes.fastest
    found = await repo.for_segments(chosen.segment_ids, budget_s=ROUTE_REPORTS_BUDGET_S)
    return [report_out(r) for r in found or []]
