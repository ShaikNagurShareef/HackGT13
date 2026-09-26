"""Edge classification and connectivity checks for the pedestrian network."""

from __future__ import annotations

import networkx as nx
import pytest
from pathpulse_data.network.graph import (
    EdgeKind,
    classify_highway,
    largest_component_share,
    road_group,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("highway", "expected"),
    [
        ("primary", EdgeKind.ROAD),
        ("residential", EdgeKind.ROAD),
        ("secondary_link", EdgeKind.ROAD),
        (["tertiary", "residential"], EdgeKind.ROAD),
        ("footway", EdgeKind.PATH),
        ("steps", EdgeKind.PATH),
        ("pedestrian", EdgeKind.PATH),
        ("service", EdgeKind.ROAD),
    ],
)
def test_classify_highway(highway: str | list[str], expected: EdgeKind) -> None:
    assert classify_highway(highway) is expected


@pytest.mark.unit
def test_classify_crossing_by_footway_tag() -> None:
    assert classify_highway("footway", footway="crossing") is EdgeKind.CROSSING


@pytest.mark.unit
@pytest.mark.parametrize(
    ("highway", "group"),
    [
        ("trunk", "arterial"),
        ("primary", "arterial"),
        ("secondary", "arterial"),
        ("tertiary", "collector"),
        ("residential", "local"),
        ("service", "local"),
        (["primary_link", "secondary"], "arterial"),
    ],
)
def test_road_group(highway: str | list[str], group: str) -> None:
    assert road_group(highway) == group


@pytest.mark.unit
def test_largest_component_share() -> None:
    g = nx.MultiDiGraph()
    g.add_edges_from([(1, 2), (2, 3), (3, 1), (10, 11)])

    assert largest_component_share(g) == pytest.approx(3 / 5)
