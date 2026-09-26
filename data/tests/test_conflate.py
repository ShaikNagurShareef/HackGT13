"""Line-to-line conflation and point aggregation onto road segments (local meters)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from pathpulse_data.network.conflate import (
    bearing_deg,
    conflate_lines,
    count_points_near,
    mean_points_near,
)
from shapely.geometry import LineString, Point

TARGET = gpd.GeoDataFrame(
    {"seg_id": [0, 1, 2]},
    geometry=[
        LineString([(0, 0), (100, 0)]),  # east-west
        LineString([(0, 0), (0, 100)]),  # north-south, shares the origin
        LineString([(500, 500), (600, 500)]),  # isolated
    ],
)


@pytest.mark.unit
def test_bearing_is_undirected_mod_180() -> None:
    assert bearing_deg(LineString([(0, 0), (10, 0)])) == pytest.approx(0.0)
    assert bearing_deg(LineString([(10, 0), (0, 0)])) == pytest.approx(0.0)
    assert bearing_deg(LineString([(0, 0), (0, 10)])) == pytest.approx(90.0)


@pytest.mark.unit
def test_conflate_prefers_parallel_line_over_closer_perpendicular() -> None:
    source = gpd.GeoDataFrame(
        {"aadt": [30000.0, 900.0]},
        geometry=[
            LineString([(0, 8), (100, 8)]),  # parallel, 8 m away from seg 0 midpoint
            LineString([(55, -50), (55, 50)]),  # perpendicular, 5 m from seg 0 midpoint
        ],
    )

    out = conflate_lines(TARGET, source, ["aadt"], max_m=20, max_angle_deg=30)

    assert out.loc[0, "aadt"] == 30000.0
    assert np.isnan(out.loc[2, "aadt"])


@pytest.mark.unit
def test_conflate_returns_nan_when_nothing_within_distance() -> None:
    source = gpd.GeoDataFrame({"v": [1.0]}, geometry=[LineString([(0, 90), (100, 90)])])

    out = conflate_lines(TARGET, source, ["v"], max_m=20, max_angle_deg=30)

    assert np.isnan(out.loc[0, "v"])


@pytest.mark.unit
def test_count_points_near_with_weights() -> None:
    pts = gpd.GeoDataFrame(
        {"ons": [10.0, 5.0, 7.0]},
        geometry=[Point(50, 3), Point(50, -4), Point(300, 300)],
    )

    counts = count_points_near(TARGET, pts, radius_m=10)
    boardings = count_points_near(TARGET, pts, radius_m=10, weight_col="ons")

    assert counts.tolist() == [2.0, 0.0, 0.0]
    assert boardings.tolist() == [15.0, 0.0, 0.0]


@pytest.mark.unit
def test_mean_points_near() -> None:
    pts = gpd.GeoDataFrame(
        {"vol": [100.0, 300.0, 50.0]},
        geometry=[Point(50, 20), Point(60, -20), Point(550, 520)],
    )

    means = mean_points_near(TARGET, pts, "vol", radius_m=30)

    assert means.loc[0] == pytest.approx(200.0)
    assert means.loc[2] == pytest.approx(50.0)
