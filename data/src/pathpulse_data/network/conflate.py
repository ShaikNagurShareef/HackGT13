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
    t_bear = np.array([bearing_deg(g) for g in target.geometry])
    best: dict[int, tuple[float, int]] = {}
    for t, s in zip(t_idx, s_idx, strict=True):
        src_line = source.geometry.iloc[s]
        local = shapely.shortest_line(mids[t], src_line)
        if _angle_diff(t_bear[t], _local_bearing(src_line, mids[t])) > max_angle_deg:
            continue
        dist = local.length
        if t not in best or dist < best[t][0]:
            best[t] = (dist, s)
    for t, (_, s) in best.items():
        out.iloc[t] = source.iloc[s][fields].to_numpy()
    return _numeric_where_possible(out)


def _numeric_where_possible(frame: pd.DataFrame) -> pd.DataFrame:
    converted = {}
    for col in frame.columns:
        numeric = pd.to_numeric(frame[col], errors="coerce")
        keep_numeric = numeric.notna().sum() == frame[col].notna().sum()
        converted[col] = numeric.astype(float) if keep_numeric else frame[col]
    return pd.DataFrame(converted, index=frame.index)


def _local_bearing(line: LineString, near: shapely.Point) -> float:
    """Bearing of the source line around the point closest to `near` (handles curves)."""
    pos = line.project(near)
    a = line.interpolate(max(pos - 10.0, 0.0))
    b = line.interpolate(min(pos + 10.0, line.length))
    if a.equals(b):
        return bearing_deg(line)
    return bearing_deg(LineString([a, b]))


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
