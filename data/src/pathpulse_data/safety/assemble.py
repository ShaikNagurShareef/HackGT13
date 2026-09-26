"""Assemble per-hex safety tables and compact per-segment / per-edge matrices for export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pathpulse_data.safety.activity import code_labels
from pathpulse_data.safety.banding import posterior_bands
from pathpulse_data.safety.dayparts import DAY_PART_KEYS, DAY_PARTS
from pathpulse_data.safety.lighting import UNKNOWN

SEGMENT_COLUMNS = ("lit", *(f"activity_{k}" for k in DAY_PART_KEYS), "help_dist_m")
EDGE_COLUMNS = ("lit", *(f"activity_{k}" for k in DAY_PART_KEYS))
UNKNOWN_DIST = -1
INT16_MAX = int(np.iinfo(np.int16).max)
SHARE_DECIMALS = 3


@dataclass(frozen=True)
class HexSafety:
    cells: pd.Index
    lat: np.ndarray
    lon: np.ndarray
    crimes_12mo: pd.DataFrame  # cells x day part, int
    crime_band: pd.DataFrame  # cells x day part, "lower" | "typical" | "higher"
    lit_share: pd.Series  # NaN where lighting coverage is too thin
    activity: pd.DataFrame  # cells x day part, band codes (-1 unknown)
    help_points: pd.Series


def crime_bands(counts: pd.DataFrame, activity: pd.DataFrame) -> pd.DataFrame:
    """Band each hex's EB-smoothed crime rate per pedestrian-hour, per day part.

    Exposure = mean hourly activity x hours in the day part. Hexes without StreetLight
    activity use the citywide median so they are neither favoured nor penalized.
    """
    hours = {p.key: len(p.hours) for p in DAY_PARTS}
    out = {}
    for key in DAY_PART_KEYS:
        act = activity[key].astype(float)
        exposure = act.fillna(act.median()).clip(lower=1e-6) * hours[key]
        out[key] = posterior_bands(counts[key].to_numpy(float), exposure.to_numpy())
    return pd.DataFrame(out, index=counts.index)


def segment_matrix(lit: np.ndarray, activity: np.ndarray, help_dist_m: np.ndarray) -> np.ndarray:
    dist = np.where(
        np.isfinite(help_dist_m), np.clip(np.round(help_dist_m), 0, INT16_MAX), UNKNOWN_DIST
    )
    return np.column_stack([lit, activity, dist]).astype(np.int16)


def edge_matrix(lit: np.ndarray, edge_seg: np.ndarray, seg_activity: np.ndarray) -> np.ndarray:
    """Per walk edge: lighting code and the activity codes of the road segment it follows."""
    act = np.full((len(edge_seg), seg_activity.shape[1]), UNKNOWN, dtype=np.int8)
    on_road = edge_seg >= 0
    act[on_road] = seg_activity[edge_seg[on_road]]
    return np.column_stack([lit, act]).astype(np.int8)


def _share(value: float) -> float | None:
    return None if not np.isfinite(value) else round(float(value), SHARE_DECIMALS)


def hexes_json(table: HexSafety) -> dict[str, Any]:
    return {
        "cells": list(table.cells),
        "lat": [round(float(v), 6) for v in table.lat],
        "lon": [round(float(v), 6) for v in table.lon],
        "crimes": {k: [int(v) for v in table.crimes_12mo[k]] for k in DAY_PART_KEYS},
        "crime_band": {k: list(table.crime_band[k]) for k in DAY_PART_KEYS},
        "lit_share": [_share(v) for v in table.lit_share.to_numpy(float)],
        "activity_band": {k: code_labels(table.activity[k].to_numpy(int)) for k in DAY_PART_KEYS},
        "help_points": [int(v) for v in table.help_points],
    }
