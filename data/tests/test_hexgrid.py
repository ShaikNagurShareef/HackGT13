"""City Pulse hex helpers."""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.citywide.hexgrid import (
    aggregate,
    cells_for,
    neighbor_sum,
    parent_blocks,
    polygon_cells,
)
from shapely.geometry import MultiPolygon, box


@pytest.mark.unit
def test_polygon_cells_cover_box_and_multipolygon() -> None:
    small = box(-84.40, 33.77, -84.39, 33.78)
    other = box(-84.30, 33.70, -84.29, 33.71)

    one = polygon_cells(small)
    both = polygon_cells(MultiPolygon([small, other]))

    assert len(one) > 5
    assert set(one) < set(both)
    assert all(h3.get_resolution(c) == 9 for c in both)


@pytest.mark.unit
def test_aggregate_sum_mean_and_count() -> None:
    cells = pd.Index(["a", "b", "c"])
    pts = ["a", "a", "b"]

    assert aggregate(cells, pts).tolist() == [2.0, 1.0, 0.0]
    assert aggregate(cells, pts, np.array([1.0, 3.0, 5.0])).tolist() == [4.0, 5.0, 0.0]
    means = aggregate(cells, pts, np.array([1.0, 3.0, 5.0]), how="mean")
    assert means.iloc[:2].tolist() == [2.0, 5.0]
    assert np.isnan(means.iloc[2])


@pytest.mark.unit
def test_neighbor_sum_excludes_self() -> None:
    center = h3.latlng_to_cell(33.775, -84.39, 9)
    ring = [c for c in h3.grid_disk(center, 1) if c != center]
    values = pd.Series({center: 10.0, ring[0]: 2.0, ring[1]: 3.0})

    out = neighbor_sum(values)

    assert out[center] == 5.0
    assert out[ring[0]] == 10.0 + (3.0 if ring[1] in h3.grid_disk(ring[0], 1) else 0.0)


@pytest.mark.unit
def test_cells_for_and_parents() -> None:
    cells = cells_for([33.775], [-84.39])

    assert h3.get_resolution(cells[0]) == 9
    assert h3.get_resolution(parent_blocks(pd.Index(cells)).iloc[0]) == 6
