"""Safety bundle loading: optional files, graceful absence, shape checks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from app.repositories.artifacts import load_bundle
from app.repositories.safety import load_safety

from tests.bundle_factory import write_bundle
from tests.safety_factory import HOT_CRIMES, write_safety


@pytest.fixture
def safety_dir(tmp_path: Path) -> Path:
    root = write_bundle(tmp_path / "pp-test-0001")
    write_safety(root)
    return root


@pytest.mark.unit
def test_old_bundle_without_safety_files_loads_as_none(bundle_dir: Path) -> None:
    bundle = load_bundle(bundle_dir)

    assert load_safety(bundle_dir, bundle.n_segments, len(bundle.graph.edge_u)) is None


@pytest.mark.unit
def test_loads_hexes_help_points_and_edge_signals(safety_dir: Path) -> None:
    bundle = load_bundle(safety_dir)

    safety = load_safety(safety_dir, bundle.n_segments, len(bundle.graph.edge_u))

    assert safety is not None
    assert int(np.sum(safety.crimes["night"])) == HOT_CRIMES
    assert len(safety.help_points) == 3
    assert safety.edges.lit.shape == (len(bundle.graph.edge_u),)
    assert safety.edges.activity.shape == (len(bundle.graph.edge_u), 4)
    assert safety.data_through == "2026-09-26"
    assert safety.cells[0] in safety.index


@pytest.mark.unit
def test_mismatched_shapes_disable_safety(safety_dir: Path) -> None:
    bundle = load_bundle(safety_dir)

    assert load_safety(safety_dir, bundle.n_segments + 1, len(bundle.graph.edge_u)) is None


@pytest.mark.unit
def test_corrupt_file_disables_safety(safety_dir: Path) -> None:
    (safety_dir / "safety_hexes.json").write_text("{not json")
    bundle_n = 12

    assert load_safety(safety_dir, bundle_n, bundle_n) is None
