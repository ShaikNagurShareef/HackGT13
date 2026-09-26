"""Assembling the safety bundle files: exposure-normalized bands and compact matrices."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.safety.assemble import (
    EDGE_COLUMNS,
    SEGMENT_COLUMNS,
    HexSafety,
    crime_bands,
    edge_matrix,
    hexes_json,
    segment_matrix,
)
from pathpulse_data.safety.dayparts import DAY_PART_KEYS
from pathpulse_data.safety.lighting import LIT, UNKNOWN, UNLIT

CELLS = pd.Index([f"89{i:013x}" for i in range(9)])


def _frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({k: values for k in DAY_PART_KEYS}, index=CELLS)


@pytest.mark.unit
def test_crime_bands_normalize_by_pedestrian_exposure() -> None:
    # Busy hexes (high activity) carry more crimes but not a higher rate per pedestrian.
    counts = _frame([30, 30, 30, 3, 3, 3, 12, 12, 12])
    activity = _frame([100, 100, 100, 10, 10, 10, 10, 10, 10])

    bands = crime_bands(counts, activity)

    assert set(bands.loc[CELLS[:3], "night"]) <= {"lower", "typical"}
    assert set(bands.loc[CELLS[6:], "night"]) == {"higher"}


@pytest.mark.unit
def test_crime_bands_impute_missing_activity_with_median() -> None:
    counts = _frame([1, 1, 1, 1, 1, 1, 1, 1, 1])
    activity = _frame([np.nan, 10, 10, 10, 10, 10, 10, 10, 10])

    bands = crime_bands(counts, activity)

    assert bands.notna().all().all()


@pytest.mark.unit
def test_segment_and_edge_matrices_carry_codes_and_neutral_unknowns() -> None:
    seg_lit = np.array([LIT, UNLIT, UNKNOWN], np.int8)
    seg_act = np.array([[0, 1, 2, 2], [2, 2, 2, 1], [-1, -1, -1, -1]], np.int8)
    help_m = np.array([12.4, np.nan, 40000.0])

    seg = segment_matrix(seg_lit, seg_act, help_m)
    edge = edge_matrix(np.array([UNKNOWN, LIT], np.int8), np.array([1, -1]), seg_act)

    assert seg.dtype == np.int16
    assert seg.shape == (3, len(SEGMENT_COLUMNS))
    assert list(seg[0]) == [LIT, 0, 1, 2, 2, 12]
    assert seg[1, -1] == -1  # unknown distance
    assert seg[2, -1] == np.iinfo(np.int16).max  # clipped, not wrapped
    assert edge.dtype == np.int8
    assert edge.shape == (2, len(EDGE_COLUMNS))
    assert list(edge[0]) == [UNKNOWN, 2, 2, 2, 1]  # activity comes from the road segment
    assert list(edge[1]) == [LIT, -1, -1, -1, -1]  # off-road path: activity unknown


@pytest.mark.unit
def test_hexes_json_is_column_oriented_with_nulls() -> None:
    cells = CELLS[:2]
    table = HexSafety(
        cells=cells,
        lat=np.array([33.7, 33.8]),
        lon=np.array([-84.4, -84.3]),
        crimes_12mo=pd.DataFrame({k: [3, 0] for k in DAY_PART_KEYS}, index=cells),
        crime_band=pd.DataFrame({k: ["higher", "lower"] for k in DAY_PART_KEYS}, index=cells),
        lit_share=pd.Series([0.625, np.nan], index=cells),
        activity=pd.DataFrame({k: [2, -1] for k in DAY_PART_KEYS}, index=cells),
        help_points=pd.Series([1, 0], index=cells),
    )

    out = json.loads(json.dumps(hexes_json(table)))

    assert out["cells"] == list(cells)
    assert out["crimes"]["night"] == [3, 0]
    assert out["crime_band"]["evening"] == ["higher", "lower"]
    assert out["lit_share"] == [0.625, None]
    assert out["activity_band"]["morning"] == ["busy", None]
    assert out["help_points"] == [1, 0]
