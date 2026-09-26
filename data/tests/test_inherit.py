"""Walk edges inherit risk from the road they follow (sidewalk) or cross (crossing)."""

from __future__ import annotations

import geopandas as gpd
import pytest
from pathpulse_data.network.inherit import NO_ROAD, inherit_segments
from shapely.geometry import LineString

ROADS = gpd.GeoDataFrame(
    {"seg_id": [100, 200]},
    geometry=[LineString([(0, 0), (200, 0)]), LineString([(0, 0), (0, 200)])],
)


@pytest.mark.unit
def test_sidewalk_inherits_parallel_road_not_cross_street() -> None:
    walk = gpd.GeoDataFrame(
        {"kind": ["path"]},
        geometry=[LineString([(20, 9), (180, 9)])],  # 9 m north of road 100
    )

    assert inherit_segments(walk, ROADS).tolist() == [100]


@pytest.mark.unit
def test_crossing_inherits_the_road_it_crosses() -> None:
    walk = gpd.GeoDataFrame(
        {"kind": ["crossing"]},
        geometry=[LineString([(100, -8), (100, 8)])],  # across road 100
    )

    assert inherit_segments(walk, ROADS).tolist() == [100]


@pytest.mark.unit
def test_path_far_from_roads_has_no_segment() -> None:
    walk = gpd.GeoDataFrame({"kind": ["path"]}, geometry=[LineString([(100, 100), (150, 150)])])

    assert inherit_segments(walk, ROADS).tolist() == [NO_ROAD]


@pytest.mark.unit
def test_road_edge_matches_its_own_centerline() -> None:
    walk = gpd.GeoDataFrame({"kind": ["road"]}, geometry=[LineString([(0, 50), (0, 150)])])

    assert inherit_segments(walk, ROADS).tolist() == [200]
