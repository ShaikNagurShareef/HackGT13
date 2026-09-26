"""Attach attributes from other agencies' layers to our road segments.

All geometries must share a projected CRS in meters. Line layers are matched by segment
midpoint distance *and* heading, so a cross street never donates its AADT or speed limit.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString


def bearing_deg(line: LineString) -> float:
    """Undirected bearing of the chord in [0, 180)."""
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0


def _angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def conflate_lines(
    target: gpd.GeoDataFrame,
    source: gpd.GeoDataFrame,
    fields: list[str],
    max_m: float = 20.0,
    max_angle_deg: float = 30.0,
) -> pd.DataFrame:
    """For each target line, copy `fields` from the nearest roughly-parallel source line."""
    mids = shapely.line_interpolate_point(target.geometry.to_numpy(), 0.5, normalized=True)
    tree = shapely.STRtree(source.geometry.to_numpy())
    t_idx, s_idx = tree.query(mids, predicate="dwithin", distance=max_m)
    out = pd.DataFrame(np.nan, index=target.index, columns=fields, dtype=object)
    if len(t_idx) == 0:
        return _numeric_where_possible(out)
    src = source.geometry.to_numpy()[s_idx]
    t_bear = _chord_bearings(target.geometry.to_numpy())[t_idx]
    s_bear = _local_bearings(src, mids[t_idx])
    diff = np.abs(t_bear - s_bear) % 180.0
    ok = np.minimum(diff, 180.0 - diff) <= max_angle_deg
    if not ok.any():
        return _numeric_where_possible(out)
    pairs = pd.DataFrame(
        {"t": t_idx[ok], "s": s_idx[ok], "d": shapely.distance(mids[t_idx[ok]], src[ok])}
    )
    best = pairs.loc[pairs.groupby("t")["d"].idxmin()]
    values = source.iloc[best["s"].to_numpy()][fields].to_numpy()
    out.iloc[best["t"].to_numpy()] = values
    return _numeric_where_possible(out)


def _chord_bearings(lines: np.ndarray) -> np.ndarray:
    """Undirected chord bearing of each line, vectorized."""
    first = shapely.get_point(lines, 0)
    last = shapely.get_point(lines, -1)
    dx = shapely.get_x(last) - shapely.get_x(first)
    dy = shapely.get_y(last) - shapely.get_y(first)
    return np.degrees(np.arctan2(dy, dx)) % 180.0


def _local_bearings(lines: np.ndarray, near: np.ndarray) -> np.ndarray:
    """Bearing of each source line within 10 m of its closest point to `near` (curves)."""
    lengths = shapely.length(lines)
    pos = shapely.line_locate_point(lines, near)
    a = shapely.line_interpolate_point(lines, np.maximum(pos - 10.0, 0.0))
    b = shapely.line_interpolate_point(lines, np.minimum(pos + 10.0, lengths))
    dx, dy = shapely.get_x(b) - shapely.get_x(a), shapely.get_y(b) - shapely.get_y(a)
    local = np.degrees(np.arctan2(dy, dx)) % 180.0
    degenerate = np.hypot(dx, dy) < 1e-9
    return np.where(degenerate, _chord_bearings(lines), local)


def _numeric_where_possible(frame: pd.DataFrame) -> pd.DataFrame:
    converted = {}
    for col in frame.columns:
        numeric = pd.to_numeric(frame[col], errors="coerce")
        keep_numeric = numeric.notna().sum() == frame[col].notna().sum()
        converted[col] = numeric.astype(float) if keep_numeric else frame[col]
    return pd.DataFrame(converted, index=frame.index)


def count_points_near(
    target: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    radius_m: float,
    weight_col: str | None = None,
) -> pd.Series:
    """Count (or sum a weight over) points within `radius_m` of each target line."""
    tree = shapely.STRtree(target.geometry.to_numpy())
    p_idx, t_idx = tree.query(points.geometry.to_numpy(), predicate="dwithin", distance=radius_m)
    weights = (
        points[weight_col].fillna(0.0).to_numpy(float)[p_idx] if weight_col else np.ones(len(p_idx))
    )
    sums = np.bincount(t_idx, weights=weights, minlength=len(target))
    return pd.Series(sums, index=target.index, dtype=float)


def mean_points_near(
    target: gpd.GeoDataFrame, points: gpd.GeoDataFrame, value_col: str, radius_m: float
) -> pd.Series:
    """Mean of `value_col` over points within `radius_m`; NaN where none."""
    total = count_points_near(target, points, radius_m, weight_col=value_col)
    count = count_points_near(target, points, radius_m)
    return (total / count.replace(0.0, np.nan)).astype(float)
