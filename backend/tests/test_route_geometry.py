"""Route polylines follow the walked direction: no backtracking or duplicated joints.

Regression: OSMnx stores most edge geometries from v to u, so flipping only reversed
traversals produced zigzags and polylines ~1.6x longer than the route distance.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
from datetime import datetime

import numpy as np
import pytest
from app.domain.router import Router
from app.domain.timeutil import ATLANTA
from app.repositories.artifacts import Bundle, WalkGraph

from tests.bundle_factory import COLS, HOT_ROW, node_id

NIGHT = datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA)
TOLERANCE = 0.03


def _polyline_m(coords: list[list[float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in itertools.pairwise(coords):
        kx = 111_320.0 * math.cos(math.radians((y1 + y2) / 2))
        total += math.hypot((x2 - x1) * kx, (y2 - y1) * 111_320.0)
    return total


def _with_midpoints(graph: WalkGraph, flip: bool) -> WalkGraph:
    """Give every edge a midpoint vertex; `flip` stores the geometry v -> u like OSMnx."""
    coords, offsets = [], [0]
    for e in range(len(graph.edge_u)):
        a = np.array([graph.node_lon[graph.edge_u[e]], graph.node_lat[graph.edge_u[e]]])
        b = np.array([graph.node_lon[graph.edge_v[e]], graph.node_lat[graph.edge_v[e]]])
        pts = [a, (a + b) / 2, b]
        coords += pts[::-1] if flip else pts
        offsets.append(len(coords))
    return dataclasses.replace(
        graph, coords=np.array(coords), coord_offsets=np.array(offsets, np.int32)
    )


@pytest.mark.unit
@pytest.mark.parametrize("flip", [False, True])
def test_polyline_length_matches_route_distance(bundle: Bundle, flip: bool) -> None:
    variant = dataclasses.replace(bundle, graph=_with_midpoints(bundle.graph, flip))
    router = Router(variant)

    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=False)

    for route in (plan.fastest, plan.pathpro):
        assert route is not None
        assert _polyline_m(route.coords) == pytest.approx(route.distance_m, rel=TOLERANCE)
        start = [variant.graph.node_lon[route.nodes[0]], variant.graph.node_lat[route.nodes[0]]]
        assert route.coords[0] == pytest.approx(start)
        pairs = itertools.pairwise(route.coords)
        assert all(a != b for a, b in pairs)  # no duplicated joint vertices


@pytest.mark.unit
def test_geometry_orientation_never_changes_route_choice(bundle: Bundle) -> None:
    plans = [
        Router(dataclasses.replace(bundle, graph=_with_midpoints(bundle.graph, flip))).plan(
            node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=False
        )
        for flip in (False, True)
    ]

    assert plans[0].fastest.nodes == plans[1].fastest.nodes
    assert plans[0].pathpro is not None and plans[1].pathpro is not None
    assert plans[0].pathpro.nodes == plans[1].pathpro.nodes
