"""Score a walking path at its true traversal times (PRD RTE-04, EC-14, EC-23)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from app.domain.scoring import HIGH_THRESHOLD, score_from_log_density
from app.domain.timeutil import cell_at
from app.repositories.artifacts import Bundle

TOP_SEGMENTS = 3
UNNAMED = "Unnamed street"


@dataclass(frozen=True)
class EdgeStep:
    edge: int
    seg_id: int
    length_m: float
    score: float


@dataclass(frozen=True)
class NamedSegment:
    seg_id: int
    name: str
    score: int
    length_m: float


@dataclass(frozen=True)
class RouteMetrics:
    nodes: list[int]
    edges: tuple[EdgeStep, ...]
    coords: list[list[float]]
    duration_s: float
    distance_m: float
    risk_score: int
    exposure: float  # expected-crash exposure along the path (density per 100 m x length)
    high_risk_m: float
    limited_data_m: float
    top_segments: tuple[NamedSegment, ...]

    @property
    def high_risk_names(self) -> set[str]:
        return {s.name for s in self.top_segments if s.score >= HIGH_THRESHOLD}


def measure_route(
    bundle: Bundle,
    path: list[int],
    edge_of: np.ndarray,
    reversed_: np.ndarray,
    time_s: np.ndarray,
    dst: np.ndarray,
    depart: datetime,
    wet: bool,
) -> RouteMetrics:
    g, meta = bundle.graph, bundle.seg_meta
    away = float(bundle.quantiles[500])
    elapsed, steps, coords, log_ds = 0.0, [], [], []
    nodes = [int(g.edge_v[edge_of[path[0]]] if reversed_[path[0]] else g.edge_u[edge_of[path[0]]])]
    for d in path:
        e = int(edge_of[d])
        mid = depart + timedelta(seconds=elapsed + time_s[d] / 2)
        seg = int(g.edge_seg[e])
        log_d = (
            float(bundle.log_density(np.array([seg]), cell_at(mid, wet))[0]) if seg >= 0 else away
        )
        log_ds.append(log_d)
        steps.append(EdgeStep(e, seg, float(g.edge_len[e]), 0.0))
        pts = g.edge_coords(e)[::-1] if reversed_[d] else g.edge_coords(e)
        coords += [[float(x), float(y)] for x, y in (pts[1:] if coords else pts)]
        nodes.append(int(dst[d]))
        elapsed += float(time_s[d])
    scores = score_from_log_density(np.array(log_ds), bundle.quantiles)
    steps = [
        EdgeStep(s.edge, s.seg_id, s.length_m, float(sc))
        for s, sc in zip(steps, scores, strict=True)
    ]
    lengths = np.array([s.length_m for s in steps])
    mean_log = float(np.log(np.sum(np.exp(log_ds) * lengths) / max(lengths.sum(), 1e-9)))
    limited = sum(
        s.length_m for s in steps if s.seg_id >= 0 and meta["confidence"][s.seg_id] == "limited"
    )
    return RouteMetrics(
        nodes=nodes,
        edges=tuple(steps),
        coords=coords,
        duration_s=elapsed,
        distance_m=float(lengths.sum()),
        risk_score=round(float(score_from_log_density(np.array([mean_log]), bundle.quantiles)[0])),
        exposure=float(np.sum(np.exp(log_ds) * lengths / 100.0)),
        high_risk_m=float(sum(s.length_m for s in steps if s.score >= HIGH_THRESHOLD)),
        limited_data_m=float(limited),
        top_segments=_top_segments(steps, np.exp(log_ds), meta),
    )


def _top_segments(
    steps: list[EdgeStep], density: np.ndarray, meta: dict
) -> tuple[NamedSegment, ...]:
    """Named stretches contributing most exposure (density x length), merged by name."""
    by_name: dict[str, tuple[float, NamedSegment]] = {}
    for step, dens in zip(steps, density, strict=True):
        if step.seg_id < 0:
            continue
        name = meta["name"][step.seg_id]
        if name == UNNAMED:
            continue  # alleys and driveways: counted in scores, not listed by name
        exposure = dens * step.length_m
        prev = by_name.get(name)
        total = exposure + (prev[0] if prev else 0.0)
        length = step.length_m + (prev[1].length_m if prev else 0.0)
        score = max(round(step.score), prev[1].score if prev else 0)
        by_name[name] = (total, NamedSegment(step.seg_id, name, score, length))
    ranked = sorted(by_name.values(), key=lambda t: t[0], reverse=True)
    return tuple(seg for _, seg in ranked[:TOP_SEGMENTS])
