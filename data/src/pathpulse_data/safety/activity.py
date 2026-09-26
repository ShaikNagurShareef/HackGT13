"""Pedestrian activity bands ("quiet" / "moderate" / "busy") from StreetLight hourly rates."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pathpulse_data.citywide.hexgrid import cells_for
from pathpulse_data.safety.dayparts import DAY_PART_KEYS

ACTIVITY_BANDS: tuple[str, str, str] = ("quiet", "moderate", "busy")
UNKNOWN_CODE = -1
LOWER_Q, UPPER_Q = 1 / 3, 2 / 3


def activity_thresholds(rates: pd.DataFrame) -> tuple[float, float]:
    """Terciles pooled over every (place, day part): nights read "quiet" against the day."""
    pooled = rates.to_numpy(float).ravel()
    pooled = pooled[np.isfinite(pooled)]
    if pooled.size == 0:
        raise RuntimeError("no StreetLight activity data available for the safety layer")
    lo, hi = np.quantile(pooled, [LOWER_Q, UPPER_Q])
    return float(lo), float(hi)


def band_codes(values: np.ndarray, thresholds: tuple[float, float]) -> np.ndarray:
    """0 quiet, 1 moderate, 2 busy, -1 unknown."""
    v = np.asarray(values, dtype=float)
    lo, hi = thresholds
    codes = np.where(v < lo, 0, np.where(v < hi, 1, 2))
    return np.where(np.isfinite(v), codes, UNKNOWN_CODE).astype(np.int8)


def code_labels(codes: np.ndarray) -> list[str | None]:
    return [ACTIVITY_BANDS[c] if c >= 0 else None for c in np.asarray(codes, dtype=int)]


def hex_activity(points: pd.DataFrame, cells: pd.Index) -> pd.DataFrame:
    """Mean hourly activity of StreetLight zones whose centroid falls in each hex."""
    keys = [k for k in DAY_PART_KEYS if k in points.columns]
    frame = points[keys].assign(cell=cells_for(points["lat"], points["lon"]))
    return frame.groupby("cell")[keys].mean().reindex(cells)
