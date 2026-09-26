"""Bundle loading, integrity checks, and log-density composition."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
from app.domain.timeutil import Cell
from app.repositories.artifacts import Bundle, BundleError, load_bundle


@pytest.mark.unit
def test_loads_all_parts(bundle: Bundle) -> None:
    assert bundle.model_version == "pp-test-0001"
    assert bundle.n_segments == 12
    assert bundle.spatial_keys == ("history", "traffic_volume", "speed")
    assert len(bundle.temporal) == 4 * 24 * 3 * 2
    assert bundle.graph.edge_coords(0).shape == (2, 2)


@pytest.mark.unit
def test_log_density_is_base_plus_spatial_plus_temporal(bundle: Bundle) -> None:
    cell = Cell("friday", 22, "dark", True)
    seg = np.array([2])

    got = bundle.log_density(seg, cell)[0]

    expected = bundle.base + bundle.spatial[2].sum() + bundle.temporal[cell.key].sum()
    assert got == pytest.approx(expected)


@pytest.mark.unit
def test_tampered_file_fails_integrity_check(bundle_dir: Path, tmp_path: Path) -> None:
    copy = tmp_path / "tampered"
    shutil.copytree(bundle_dir, copy)
    (copy / "seg_meta.json").write_text("{}")

    with pytest.raises(BundleError, match="sha256"):
        load_bundle(copy)


@pytest.mark.unit
def test_missing_bundle_raises(tmp_path: Path) -> None:
    with pytest.raises(BundleError, match="no manifest"):
        load_bundle(tmp_path / "nope")
