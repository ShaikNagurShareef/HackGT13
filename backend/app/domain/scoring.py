"""Citywide 0-100 score scale, bands, and exact factor attribution (PRD EXP-01, §7.3).

Attribution telescopes through the percentile curve: factors are added one at a time from
largest |effect| to smallest, and each gets the change in score it causes. The bars
therefore sum exactly to the displayed score with no division by near-zero totals.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

HIGH_THRESHOLD = 75
ELEVATED_THRESHOLD = 50
MODERATE_THRESHOLD = 25


class Band(StrEnum):
    LOWER = "Lower"
    MODERATE = "Moderate"
    ELEVATED = "Elevated"
    HIGH = "High"


def band_for(score: int) -> Band:
    if score >= HIGH_THRESHOLD:
        return Band.HIGH
    if score >= ELEVATED_THRESHOLD:
        return Band.ELEVATED
    if score >= MODERATE_THRESHOLD:
        return Band.MODERATE
    return Band.LOWER


def score_from_log_density(log_density: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    grid = np.linspace(0.0, 100.0, len(quantiles))
    return np.interp(np.asarray(log_density, dtype=float), quantiles, grid)


def score_one(log_density: float, quantiles: np.ndarray) -> float:
    return float(score_from_log_density(np.array([log_density]), quantiles)[0])


@dataclass(frozen=True)
class FactorPoints:
    key: str
    points: int


@dataclass(frozen=True)
class Attribution:
    score: int
    baseline_points: int
    factors: tuple[FactorPoints, ...]
    remainder_points: int


def attribute(
    base: float, factors: dict[str, float], quantiles: np.ndarray, top_n: int = 5
) -> Attribution:
    """Split a score into baseline + top-N factor points + remainder (integers, exact sum)."""
    ordered = sorted(factors.items(), key=lambda kv: abs(kv[1]), reverse=True)
    cumulative = base
    prev = score_one(base, quantiles)
    raw: list[tuple[str, float]] = []
    for key, value in ordered:
        cumulative += value
        now = score_one(cumulative, quantiles)
        raw.append((key, now - prev))
        prev = now
    score = round(prev)
    baseline = round(score_one(base, quantiles))
    shown = [FactorPoints(k, round(p)) for k, p in raw[:top_n]]
    remainder = score - baseline - sum(f.points for f in shown)
    return Attribution(
        score=score, baseline_points=baseline, factors=tuple(shown), remainder_points=remainder
    )
