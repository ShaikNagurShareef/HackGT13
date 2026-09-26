"""Multi-mode loading and routing: walk + ride (bike / e-bike / scooter) share one code path."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from app.domain.modes import MODES, RIDE_PREFIX, mode_for
from app.domain.router import WALK_SPEED_MPS, Router
from app.domain.timeutil import ATLANTA
from app.repositories.artifacts import load_bundle, load_ride_bundle

from tests.bundle_factory import CALM_ROW, HOT_ROW, RIDE_COLS, ride_node_id

NIGHT = datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA)


@pytest.mark.unit
def test_modes_catalog_matches_the_api_contract() -> None:
    assert list(MODES) == ["walk", "bike", "ebike", "scooter"]
    assert [m.label for m in MODES.values()] == ["Walk", "Bike", "E-bike", "Scooter"]
    assert MODES["walk"].speed_kmh == pytest.approx(WALK_SPEED_MPS * 3.6)
    assert [MODES[k].speed_kmh for k in ("bike", "ebike", "scooter")] == [15, 22, 18]
    assert [m.network for m in MODES.values()] == ["walk", "ride", "ride", "ride"]
    assert [m.static_prefix for m in MODES.values()] == ["", "ride_", "ride_", "ride_"]
    assert mode_for("ebike").speed_mps == pytest.approx(22 / 3.6)


@pytest.mark.unit
def test_ride_bundle_loads_by_prefix_through_the_same_loader(ride_bundle_dir: Path) -> None:
    walk = load_bundle(ride_bundle_dir)
    ride = load_bundle(ride_bundle_dir, prefix=RIDE_PREFIX)

    assert walk.prefix == "" and ride.prefix == RIDE_PREFIX
    assert walk.n_segments == 12
    assert ride.n_segments == 17
    assert len(ride.graph.node_lon) == 3 * RIDE_COLS
    assert ride.model_version == walk.model_version
    assert ride.metrics["headline"]["roc_auc"] == 0.83


@pytest.mark.unit
def test_ride_bundle_is_none_when_ride_files_are_absent(bundle_dir: Path) -> None:
    assert load_ride_bundle(bundle_dir) is None


@pytest.mark.unit
def test_corrupt_ride_file_disables_ride_but_never_walk(
    ride_bundle_dir: Path, tmp_path: Path
) -> None:
    root = Path(shutil.copytree(ride_bundle_dir, tmp_path / "copy"))
    (root / "ride_spatial_factors.npy").write_bytes(b"not numpy")

    assert load_ride_bundle(root) is None
    assert load_bundle(root).n_segments == 12


@pytest.mark.unit
def test_ride_bundle_with_out_of_range_segments_is_rejected(
    ride_bundle_dir: Path, tmp_path: Path
) -> None:
    root = Path(shutil.copytree(ride_bundle_dir, tmp_path / "copy"))
    meta = json.loads((root / "ride_seg_meta.json").read_text())
    (root / "ride_seg_meta.json").write_text(json.dumps({k: v[:5] for k, v in meta.items()}))
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["files"].pop("ride_seg_meta.json")
    (root / "manifest.json").write_text(json.dumps(manifest))

    assert load_ride_bundle(root) is None


@pytest.mark.unit
def test_ride_router_uses_mode_speed_and_the_same_detour_rule(ride_bundle_dir: Path) -> None:
    ride = load_bundle(ride_bundle_dir, prefix=RIDE_PREFIX)
    router = Router(ride)
    origin, dest = ride_node_id(HOT_ROW, 0), ride_node_id(HOT_ROW, 2)

    plan = router.plan(origin, dest, NIGHT, wet=False, profile=mode_for("bike").profile)

    speed = 15 / 3.6
    assert plan.fastest.duration_s == pytest.approx(plan.fastest.distance_m / speed, rel=1e-3)
    assert plan.pathpro is not None
    assert ride_node_id(CALM_ROW, 1) in plan.pathpro.nodes
    budget = min(plan.fastest.duration_s * 1.25, plan.fastest.duration_s + 360)
    assert plan.pathpro.duration_s <= budget + 1e-6


@pytest.mark.unit
def test_ride_trips_are_long_only_past_the_ride_threshold() -> None:
    walk_profile, bike_profile = mode_for("walk").profile, mode_for("bike").profile

    assert walk_profile.speed_mps == WALK_SPEED_MPS
    assert bike_profile.long_trip_m > walk_profile.long_trip_m
