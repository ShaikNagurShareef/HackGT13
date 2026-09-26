"""Personal-safety signals: day parts, after-dark test, and the lit-and-busy cost term.

Only lighting and foot traffic reach routing. Reported crime is informational and has no
path into this module's cost term (see repositories/safety.py: EdgeSignals holds no crime).
Day parts mirror the data pipeline (pathpulse_data/safety/dayparts.py).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from app.domain.timeutil import ATLANTA, light_at

DAY_PART_HOURS: dict[str, tuple[int, ...]] = {
    "night": (22, 23, 0, 1, 2, 3, 4, 5),
    "morning": tuple(range(6, 12)),
    "afternoon": tuple(range(12, 18)),
    "evening": tuple(range(18, 22)),
}
DAY_PART_KEYS: tuple[str, ...] = tuple(DAY_PART_HOURS)
_BY_HOUR = {h: key for key, hours in DAY_PART_HOURS.items() for h in hours}

LIT, UNLIT, UNKNOWN = 1, 0, -1
QUIET, MODERATE, BUSY = 0, 1, 2
UNLIT_PENALTY = 1.0  # an unlit metre costs like two metres after dark
QUIET_PENALTY = 0.5  # a quiet metre costs like one and a half
MIN_KNOWN_SHARE = 0.5
M_PER_DEG = 111_320.0


@dataclass(frozen=True)
class EdgeSignals:
    """Per walk edge: lighting code and activity band code per day part. No crime."""

    lit: np.ndarray  # int8: 1 lit, 0 unlit, -1 unknown
    activity: np.ndarray  # int8, n_edges x 4 day parts: 0 quiet, 1 moderate, 2 busy, -1

    def activity_for(self, day_part: str) -> np.ndarray:
        return self.activity[:, DAY_PART_KEYS.index(day_part)]


def day_part_for_hour(hour: int) -> str:
    if hour not in _BY_HOUR:
        raise ValueError(f"hour must be 0..23, got {hour}")
    return _BY_HOUR[hour]


def day_part_at(ts: datetime) -> str:
    return day_part_for_hour(ts.astimezone(ATLANTA).hour)


def is_after_dark(ts: datetime) -> bool:
    """Between sunset and sunrise at the coverage centroid (same astral rule as the model)."""
    return light_at(ts.astimezone(ATLANTA)) != "day"


def signal_penalty(signals: EdgeSignals, day_part: str) -> np.ndarray:
    """Per undirected edge: 1 + penalties for known-unlit and known-quiet; unknown is neutral."""
    unlit = signals.lit == UNLIT
    quiet = signals.activity_for(day_part) == QUIET
    return np.asarray(1.0 + UNLIT_PENALTY * unlit + QUIET_PENALTY * quiet, dtype=float)


def known_share(lengths: np.ndarray, codes: np.ndarray, target: int) -> float | None:
    """Share of known-signal length equal to `target`; None when under half is known."""
    total = float(np.sum(lengths))
    known = codes != UNKNOWN
    known_len = float(np.sum(lengths[known]))
    if total <= 0 or known_len < MIN_KNOWN_SHARE * total:
        return None
    return float(np.sum(lengths[codes == target]) / known_len)


def busier_share(lengths: np.ndarray, activity: np.ndarray) -> float | None:
    """Share of known-activity length that is moderate or busy ("busier" than quiet)."""
    busier = np.where(activity == UNKNOWN, UNKNOWN, (activity >= MODERATE).astype(int))
    return known_share(lengths, busier, 1)


def densify(coords: list[list[float]], step_m: float) -> np.ndarray:
    """Points along a lon/lat polyline no more than ~`step_m` apart (vertices kept)."""
    pts = np.asarray(coords, dtype=float)
    if len(pts) < 2:
        return pts
    out = [pts[:1]]
    for a, b in itertools.pairwise(pts):
        kx = M_PER_DEG * math.cos(math.radians((a[1] + b[1]) / 2))
        dist = math.hypot((b[0] - a[0]) * kx, (b[1] - a[1]) * M_PER_DEG)
        n = max(1, math.ceil(dist / step_m))
        t = np.linspace(0, 1, n + 1)[1:, None]
        out.append(a + t * (b - a))
    return np.vstack(out)
