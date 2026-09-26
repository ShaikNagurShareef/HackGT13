"""Segment detail: score, confidence, factor attribution, and crash history (EXP-01..03)."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from app.api.envelope import AppError
from app.api.schemas import ConditionUsed, FactorOut, HistoryOut, SegmentDetail
from app.domain.scoring import attribute, band_for
from app.domain.timeutil import cell_at
from app.repositories.artifacts import Bundle
from app.services.weather import Resolved

TOP_FACTORS = 5
HISTORY_PERIOD = "2020-2024"


def factor_values(bundle: Bundle, seg_id: int, key: tuple[str, int, str, bool]) -> dict[str, float]:
    spatial = dict(zip(bundle.spatial_keys, bundle.spatial[seg_id], strict=True))
    temporal = dict(zip(bundle.temporal_keys, bundle.temporal[key], strict=True))
    return {k: float(v) for k, v in {**spatial, **temporal}.items()}


def segment_detail(bundle: Bundle, seg_id: int, at: datetime, resolved: Resolved) -> SegmentDetail:
    if not 0 <= seg_id < bundle.n_segments:
        raise AppError("NOT_FOUND", "That street segment is not in PathPulse coverage.", status=404)
    cell = cell_at(at, resolved.wet)
    factors = factor_values(bundle, seg_id, cell.key)
    result = attribute(bundle.base, factors, bundle.quantiles, top_n=TOP_FACTORS)
    labels = {**bundle.spatial_labels, **bundle.temporal_labels}
    meta = bundle.seg_meta
    log_d = float(bundle.log_density(np.array([seg_id]), cell)[0])
    assert np.isfinite(log_d)
    return SegmentDetail(
        seg_id=seg_id,
        name=meta["name"][seg_id],
        road_group=meta["road_group"][seg_id],
        score=result.score,
        band=band_for(result.score).value,
        confidence=meta["confidence"][seg_id],
        baseline_points=result.baseline_points,
        factors=[
            FactorOut(key=f.key, label=labels[f.key], points=f.points) for f in result.factors
        ],
        remainder_points=result.remainder_points,
        history=HistoryOut(
            crashes=meta["crashes"][seg_id],
            ped_crashes=meta["ped_crashes"][seg_id],
            dark_share=meta["dark_share"][seg_id],
            wet_share=meta["wet_share"][seg_id],
            period=HISTORY_PERIOD,
        ),
        condition_used=ConditionUsed(
            cond="wet" if resolved.wet else "dry",
            source=resolved.source,
            label=resolved.label,  # type: ignore[arg-type]
        ),
        at=at.isoformat(),
    )
