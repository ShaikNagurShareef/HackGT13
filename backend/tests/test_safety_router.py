"""The well-lit and busier preference: after dark only, detour budget kept, crime never used."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from app.domain.router import Router
from app.domain.timeutil import ATLANTA
from app.repositories.artifacts import Bundle, load_bundle
from app.repositories.safety import SafetyBundle, load_safety

from tests.bundle_factory import COLS, HOT_ROW, ROWS, node_id, write_bundle
from tests.safety_factory import LIT, UNLIT, write_safety

NIGHT = datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA)
NOON = datetime(2026, 9, 25, 12, 0, tzinfo=ATLANTA)
ORIGIN, DEST = node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1)
TOP, BOTTOM = 0, ROWS - 1


def _load(root: Path) -> tuple[Bundle, SafetyBundle]:
    bundle = load_bundle(root)
    safety = load_safety(root, bundle.n_segments, len(bundle.graph.edge_u))
    assert safety is not None
    return bundle, safety


@pytest.fixture
def lit_router(tmp_path: Path) -> Router:
    root = write_bundle(tmp_path / "pp-test-0001")
    write_safety(root)
    bundle, safety = _load(root)
    return Router(bundle, safety.edges)


@pytest.mark.unit
def test_default_preference_ignores_signals(lit_router: Router, bundle: Bundle) -> None:
    plain = Router(bundle).plan(ORIGIN, DEST, NIGHT, wet=False)

    plan = lit_router.plan(ORIGIN, DEST, NIGHT, wet=False)

    assert plan.pathpro is not None and plain.pathpro is not None
    assert plan.pathpro.nodes == plain.pathpro.nodes
    assert node_id(TOP, 1) in plan.pathpro.nodes  # the calm (but unlit, quiet) top row


@pytest.mark.unit
def test_lit_and_busy_detours_via_lit_busy_street_after_dark(lit_router: Router) -> None:
    plan = lit_router.plan(ORIGIN, DEST, NIGHT, wet=False, prefer="lit_and_busy")

    assert plan.pathpro is not None
    assert node_id(BOTTOM, 1) in plan.pathpro.nodes
    assert node_id(TOP, 1) not in plan.pathpro.nodes
    fastest = plan.fastest.duration_s
    assert plan.pathpro.duration_s <= min(fastest * 1.25, fastest + 360) + 1e-6


@pytest.mark.unit
def test_lit_and_busy_by_day_behaves_like_default(lit_router: Router) -> None:
    default = lit_router.plan(ORIGIN, DEST, NOON, wet=False)

    plan = lit_router.plan(ORIGIN, DEST, NOON, wet=False, prefer="lit_and_busy")

    assert plan == default


@pytest.mark.unit
def test_lit_and_busy_without_signals_behaves_like_default(bundle: Bundle) -> None:
    router = Router(bundle)

    plan = router.plan(ORIGIN, DEST, NIGHT, wet=False, prefer="lit_and_busy")

    assert plan == router.plan(ORIGIN, DEST, NIGHT, wet=False)


@pytest.mark.unit
def test_lit_and_busy_falls_back_when_no_street_is_better_lit(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "pp-test-0001")
    write_safety(root, lit={TOP: LIT, BOTTOM: UNLIT})  # the traffic pick is also the lit one
    bundle, safety = _load(root)
    router = Router(bundle, safety.edges)

    plan = router.plan(ORIGIN, DEST, NIGHT, wet=False, prefer="lit_and_busy")

    assert plan.pathpro is not None
    assert node_id(BOTTOM, 1) not in plan.pathpro.nodes


@pytest.mark.unit
def test_crime_counts_never_change_the_route(tmp_path: Path) -> None:
    plans = []
    for scale in (0, 1, 1000):
        root = write_bundle(tmp_path / f"pp-test-{scale}")
        write_safety(root, crimes_scale=scale)
        bundle, safety = _load(root)
        router = Router(bundle, safety.edges)
        plans.append(
            [router.plan(ORIGIN, DEST, NIGHT, wet=False, prefer=p) for p in Router.PREFERENCES]
        )

    assert plans[0] == plans[1] == plans[2]
