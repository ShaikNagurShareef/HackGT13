"""Snap crashes to road edges: node-first split, then nearest edge, else drop (EC-32)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.ingest.snap import RoadIndex, snap_points
from shapely.geometry import LineString

# A plus-shaped intersection at node 0 (0,0) in local meters, arms 100 m long, plus a
# lone east-west road 200 m north. Degree of node 0 = 4 road edges.
EDGES = pd.DataFrame(
    {
        "seg_id": [10, 11, 12, 13, 14],
        "u": [0, 0, 0, 0, 5],
        "v": [1, 2, 3, 4, 6],
        "geometry": [
            LineString([(0, 0), (100, 0)]),
            LineString([(0, 0), (-100, 0)]),
            LineString([(0, 0), (0, 100)]),
            LineString([(0, 0), (0, -100)]),
            LineString([(-100, 200), (100, 200)]),
        ],
    }
)
NODES = pd.DataFrame(
    {
        "node": [0, 1, 2, 3, 4, 5, 6],
        "x": [0, 100, -100, 0, 0, -100, 100],
        "y": [0, 0, 0, 100, -100, 200, 200],
    }
)


@pytest.fixture
def index() -> RoadIndex:
    return RoadIndex.from_frames(EDGES, NODES)


@pytest.mark.unit
def test_point_near_intersection_splits_across_incident_edges(index: RoadIndex) -> None:
    out = snap_points(index, np.array([[5.0, 5.0]]))

    assert sorted(out["seg_id"].tolist()) == [10, 11, 12, 13]
    assert out["weight"].sum() == pytest.approx(1.0)
    assert out["weight"].tolist() == pytest.approx([0.25] * 4)
    assert (out["point_idx"] == 0).all()


@pytest.mark.unit
def test_point_mid_block_snaps_to_nearest_edge(index: RoadIndex) -> None:
    out = snap_points(index, np.array([[60.0, 10.0]]))

    assert out["seg_id"].tolist() == [10]
    assert out["weight"].tolist() == [1.0]
    assert out["dist_m"].iloc[0] == pytest.approx(10.0)


@pytest.mark.unit
def test_point_too_far_is_dropped(index: RoadIndex) -> None:
    out = snap_points(index, np.array([[60.0, 100.0]]))  # 100 m from arm, 100 m from north road

    assert out.empty


@pytest.mark.unit
def test_weights_sum_to_one_per_point(index: RoadIndex) -> None:
    pts = np.array([[5.0, 5.0], [60.0, 10.0], [0.0, 190.0], [60.0, 100.0]])

    out = snap_points(index, pts)

    sums = out.groupby("point_idx")["weight"].sum()
    assert sums.to_dict() == pytest.approx({0: 1.0, 1: 1.0, 2: 1.0})
