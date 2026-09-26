"""Risk-aware routing on the tiny grid: budget, single-route rule, traversal scoring."""

from __future__ import annotations

from datetime import datetime

import pytest
from app.domain.router import Router, RoutingError
from app.domain.timeutil import ATLANTA
from app.repositories.artifacts import Bundle

from tests.bundle_factory import CALM_ROW, COLS, HOT_ROW, node_id

NIGHT = datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA)


@pytest.fixture(scope="module")
def router(bundle: Bundle) -> Router:
    return Router(bundle)


@pytest.mark.unit
def test_snap_finds_nearest_node(router: Router, bundle: Bundle) -> None:
    lon, lat = bundle.graph.node_lon[4], bundle.graph.node_lat[4]

    node, dist = router.snap(lon + 0.00001, lat)

    assert node == 4
    assert dist < 5


@pytest.mark.unit
def test_fastest_takes_hot_corridor_and_pathpro_detours(router: Router) -> None:
    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=False)

    assert plan.fastest.nodes == [node_id(HOT_ROW, c) for c in range(COLS)]
    assert plan.pathpro is not None
    assert node_id(CALM_ROW, 1) in plan.pathpro.nodes
    assert plan.pathpro.exposure <= plan.fastest.exposure * 0.85
    assert plan.pathpro.risk_score < plan.fastest.risk_score


@pytest.mark.unit
def test_pathpro_route_respects_detour_budget(router: Router) -> None:
    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=True)

    assert plan.pathpro is not None
    fastest = plan.fastest.duration_s
    assert plan.pathpro.duration_s <= min(fastest * 1.25, fastest + 360) + 1e-6


@pytest.mark.unit
def test_calm_trip_returns_single_route(router: Router) -> None:
    plan = router.plan(node_id(CALM_ROW, 0), node_id(CALM_ROW, COLS - 1), NIGHT, wet=False)

    assert plan.pathpro is None
    assert plan.message_code == "fastest_is_lower_risk"


@pytest.mark.unit
def test_route_metrics_are_consistent(router: Router) -> None:
    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=False)
    route = plan.fastest

    assert route.distance_m == pytest.approx(sum(e.length_m for e in route.edges))
    assert 0 <= route.high_risk_m <= route.distance_m
    assert len(route.coords) >= len(route.nodes)
    assert route.top_segments[0].name == f"Row {HOT_ROW} St"


@pytest.mark.unit
def test_same_origin_and_destination_rejected(router: Router) -> None:
    with pytest.raises(RoutingError) as err:
        router.plan(3, 3, NIGHT, wet=False)
    assert err.value.code == "TOO_CLOSE"


@pytest.mark.unit
def test_search_area_covers_small_trips(router: Router) -> None:
    area = router._search_area(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1))

    assert area.all()  # the tiny grid is well inside the 1.2 km minimum padding


@pytest.mark.unit
def test_falls_back_to_full_graph_when_search_area_cuts_the_route(
    router: Router, monkeypatch: pytest.MonkeyPatch
) -> None:
    import numpy as np

    monkeypatch.setattr(router, "_search_area", lambda o, d: np.zeros(len(router.src), bool))

    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=False)

    assert plan.fastest.nodes[0] == node_id(HOT_ROW, 0)


def _with_parallel_edge(bundle: Bundle, edge: int, length_ratio: float) -> Bundle:
    """Add a second, reversed copy of `edge` (same street) with a scaled length."""
    import dataclasses

    import numpy as np

    g = bundle.graph
    pts = g.edge_coords(edge)[::-1]
    graph = dataclasses.replace(
        g,
        edge_u=np.append(g.edge_u, g.edge_v[edge]),
        edge_v=np.append(g.edge_v, g.edge_u[edge]),
        edge_len=np.append(g.edge_len, g.edge_len[edge] * length_ratio),
        edge_seg=np.append(g.edge_seg, g.edge_seg[edge]),
        edge_kind=np.append(g.edge_kind, g.edge_kind[edge]),
        coords=np.vstack([g.coords, pts]),
        coord_offsets=np.append(g.coord_offsets, g.coord_offsets[-1] + len(pts)),
    )
    return dataclasses.replace(bundle, graph=graph)


@pytest.mark.unit
@pytest.mark.parametrize(("ratio", "saved"), [(3.0, False), (0.5, True)])
def test_parallel_edges_resolve_to_the_cheaper_one(
    bundle: Bundle, ratio: float, saved: bool
) -> None:
    origin, dest = node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1)
    first_hot = next(
        e
        for e in range(len(bundle.graph.edge_u))
        if {int(bundle.graph.edge_u[e]), int(bundle.graph.edge_v[e])} == {origin, origin + 1}
    )
    base = Router(bundle).plan(origin, dest, NIGHT, wet=False).fastest

    plan = Router(_with_parallel_edge(bundle, first_hot, ratio)).plan(
        origin, dest, NIGHT, wet=False
    )

    expected = base.distance_m - (0.5 * bundle.graph.edge_len[first_hot] if saved else 0.0)
    assert plan.fastest.distance_m == pytest.approx(expected, rel=1e-4)
    assert plan.fastest.nodes == base.nodes
