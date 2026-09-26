"""Lighting joins: OSM lit tags, mapped lamps, and honest (null) coverage per hex."""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.safety.lighting import (
    LIT,
    UNKNOWN,
    UNLIT,
    edge_lit,
    hex_lit_share,
    lamps_near,
    parse_lit,
)
from shapely.geometry import LineString, Point

LAT, LON = 33.7756, -84.3963


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tag", "code"),
    [
        ("yes", LIT),
        ("24/7", LIT),
        ("automatic", LIT),
        ("sunset-sunrise", LIT),
        ("no", UNLIT),
        ("disused", UNLIT),
        ("limited", UNKNOWN),
        ("no;yes", UNKNOWN),
        (None, UNKNOWN),
        (float("nan"), UNKNOWN),
        ("<NA>", UNKNOWN),
    ],
)
def test_parse_lit(tag: object, code: int) -> None:
    assert parse_lit(tag) == code


@pytest.mark.unit
def test_lamps_near_marks_lines_within_radius() -> None:
    lines = [LineString([(0, 0), (100, 0)]), LineString([(0, 500), (100, 500)])]
    lamps = [Point(50, 10)]

    near = lamps_near(lines, lamps, radius_m=25.0)

    assert list(near) == [True, False]


@pytest.mark.unit
def test_lamps_near_with_no_lamps_is_all_false() -> None:
    near = lamps_near([LineString([(0, 0), (1, 0)])], [], radius_m=25.0)

    assert list(near) == [False]


@pytest.mark.unit
def test_edge_lit_prefers_own_tag_then_segment_then_lamps() -> None:
    own = np.array([UNLIT, UNKNOWN, UNKNOWN, UNKNOWN], np.int8)
    segment = np.array([LIT, LIT, UNKNOWN, UNKNOWN], np.int8)
    lamp = np.array([True, False, True, False])

    out = edge_lit(own, segment, lamp)

    assert list(out) == [UNLIT, LIT, LIT, UNKNOWN]


@pytest.mark.unit
def test_hex_lit_share_is_null_without_enough_known_length() -> None:
    cell = h3.latlng_to_cell(LAT, LON, 9)
    thin = sorted(set(h3.grid_disk(cell, 1)) - {cell})[0]
    edges = pd.DataFrame(
        {
            "cell": [cell, cell, cell, thin, thin],
            "length": [100.0, 100.0, 50.0, 10.0, 990.0],
            "lit": [LIT, UNLIT, LIT, LIT, UNKNOWN],
        }
    )

    share = hex_lit_share(edges, pd.Index([cell, thin]), min_known_share=0.5)

    assert share.loc[cell] == pytest.approx(150 / 250)
    assert np.isnan(share.loc[thin])  # 1% known is not enough to say anything
