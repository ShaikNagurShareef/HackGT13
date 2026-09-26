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
def test_fastest_takes_hot_corridor_and_pathpulse_detours(router: Router) -> None:
    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=False)

    assert plan.fastest.nodes == [node_id(HOT_ROW, c) for c in range(COLS)]
    assert plan.pathpulse is not None
    assert node_id(CALM_ROW, 1) in plan.pathpulse.nodes
    assert plan.pathpulse.exposure <= plan.fastest.exposure * 0.85
    assert plan.pathpulse.risk_score < plan.fastest.risk_score


@pytest.mark.unit
def test_pathpulse_route_respects_detour_budget(router: Router) -> None:
    plan = router.plan(node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1), NIGHT, wet=True)

    assert plan.pathpulse is not None
    fastest = plan.fastest.duration_s
    assert plan.pathpulse.duration_s <= min(fastest * 1.25, fastest + 360) + 1e-6


@pytest.mark.unit
def test_calm_trip_returns_single_route(router: Router) -> None:
    plan = router.plan(node_id(CALM_ROW, 0), node_id(CALM_ROW, COLS - 1), NIGHT, wet=False)

    assert plan.pathpulse is None
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
