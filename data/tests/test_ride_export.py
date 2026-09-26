"""Ride files join a NEW bundle version beside the walk model; walk files stay byte-identical."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.export.assemble import Assembled
from pathpulse_data.export.factors import Decomposition
from pathpulse_data.export.writers import write_factors, write_frames
from pathpulse_data.ride.bundle import (
    RIDE_PREFIX,
    new_ride_version,
    register_ride,
    ride_name,
    verify_unchanged,
    walk_files,
    walk_summary,
)
from pathpulse_data.ride.spec import RIDE_SPEC

WALK = {
    "segments.geojson": b'{"type":"FeatureCollection","features":[]}',
    "seg_meta.json": b'{"name":["A"]}',
    "factors.json": b"{}",
    "spatial_factors.npy": b"\x93NUMPY",
    "walk_graph.npz": b"PK\x03\x04",
    "hotspot_nodes.json": b"[]",
    "metrics.json": b'{"headline":{"capture_top10":0.74}}',
    "frames_weekday_dry.bin": bytes(range(24)),
    "hex_cells.json": b"[]",
    "safety_meta.json": b"{}",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "pp-20260926-1723-abc"
    root.mkdir()
    for name, blob in WALK.items():
        (root / name).write_bytes(blob)
    files = {name: hashlib.sha256(blob).hexdigest() for name, blob in WALK.items()}
    manifest = {"model_version": root.name, "n_segments": 1, "files": files}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def _hashes(root: Path) -> dict[str, str]:
    return {p.name: _sha(p) for p in root.iterdir() if p.name != "manifest.json"}


@pytest.mark.unit
def test_ride_names_mirror_walk_files() -> None:
    assert ride_name("walk_graph.npz") == "ride_graph.npz"
    assert ride_name("frames_friday_wet.bin") == "ride_frames_friday_wet.bin"
    assert ride_name("seg_meta.json") == "ride_seg_meta.json"
    assert RIDE_PREFIX == "ride_"


@pytest.mark.unit
def test_walk_files_are_the_walk_model_outputs_only(source: Path) -> None:
    names = walk_files(json.loads((source / "manifest.json").read_text()))

    assert "walk_graph.npz" in names
    assert "frames_weekday_dry.bin" in names
    assert "hex_cells.json" not in names
    assert "safety_meta.json" not in names


@pytest.mark.unit
def test_new_version_copies_every_file_byte_for_byte(source: Path) -> None:
    out = new_ride_version(source, "pp-20260927-0100-def")

    manifest = json.loads((out / "manifest.json").read_text())
    assert out.name == "pp-20260927-0100-def"
    assert manifest["model_version"] == out.name
    assert manifest["derived_from"] == source.name
    assert _hashes(out) == _hashes(source)
    assert verify_unchanged(source, out) == []


@pytest.mark.unit
def test_new_version_refuses_to_overwrite(source: Path) -> None:
    new_ride_version(source, "pp-x")

    with pytest.raises(FileExistsError):
        new_ride_version(source, "pp-x")


@pytest.mark.unit
def test_verify_unchanged_detects_a_modified_walk_file(source: Path) -> None:
    out = new_ride_version(source, "pp-y")
    (out / "frames_weekday_dry.bin").write_bytes(b"tampered")

    assert verify_unchanged(source, out) == ["frames_weekday_dry.bin"]


def _assembled(n_seg: int = 3) -> Assembled:
    idx = pd.MultiIndex.from_tuples(
        [("weekday", h, "day", False) for h in range(2)],
        names=["day_group", "hour", "light", "wet"],
    )
    spatial = pd.DataFrame(0.1, index=range(n_seg), columns=list(RIDE_SPEC.spatial))
    temporal = pd.DataFrame(0.0, index=idx, columns=list(RIDE_SPEC.temporal))
    frames = {"weekday_dry": np.arange(24 * n_seg, dtype=np.uint8) % 101}
    return Assembled(
        decomposition=Decomposition(base=-5.0, spatial=spatial, temporal=temporal),
        quantiles=np.linspace(-9, 0, 1001),
        frames=frames,
        reference_dates={"weekday": "2026-09-28"},
        frame_light={"weekday": ["day"] * 24},
        expected=pd.DataFrame({"spf": [1.0] * n_seg, "eb": [1.0] * n_seg}),
        temporal_effects={"dark": 1.5},
    )


@pytest.mark.unit
def test_prefixed_writers_add_ride_files_and_leave_walk_files_untouched(source: Path) -> None:
    out = new_ride_version(source, "pp-z")
    before = _hashes(out)

    write_frames(out, _assembled(), prefix=RIDE_PREFIX)
    write_factors(out, _assembled(), spec=RIDE_SPEC, prefix=RIDE_PREFIX)

    after = _hashes(out)
    assert {k: after[k] for k in before} == before
    added = set(after) - set(before)
    assert added == {"ride_frames_weekday_dry.bin", "ride_factors.json", "ride_spatial_factors.npy"}
    factors = json.loads((out / "ride_factors.json").read_text())
    assert [f["key"] for f in factors["spatial"]] == list(RIDE_SPEC.spatial)
    assert len(factors["quantiles"]) == 1001


@pytest.mark.unit
def test_register_ride_records_sha256_and_modes(source: Path) -> None:
    out = new_ride_version(source, "pp-r")
    (out / "ride_seg_meta.json").write_text('{"name":["A"]}')
    (out / "ride_graph.npz").write_bytes(b"PK")
    ride = {"model": "cyclist crashes", "headline": {"capture_top10": 0.5}, "exposure": "proxy"}

    register_ride(out, ["ride_seg_meta.json", "ride_graph.npz"], ride, extra={"ride_graph": {}})

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["files"]["ride_graph.npz"] == _sha(out / "ride_graph.npz")
    assert manifest["files"]["segments.geojson"] == _sha(source / "segments.geojson")
    assert manifest["modes"]["ride"]["files"] == ["ride_graph.npz", "ride_seg_meta.json"]
    assert manifest["modes"]["ride"]["exposure"] == "proxy"
    assert manifest["modes"]["walk"]["model"] == "pedestrian crashes"
    assert manifest["modes"]["walk"]["headline"] == {"capture_top10": 0.74}
    assert "walk_graph.npz" in manifest["modes"]["walk"]["files"]
    assert manifest["ride_graph"] == {}
    assert verify_unchanged(source, out) == []


@pytest.mark.unit
def test_register_ride_rejects_unprefixed_or_missing_files(source: Path) -> None:
    out = new_ride_version(source, "pp-s")
    ride = {"model": "cyclist crashes", "headline": {}, "exposure": "proxy"}

    with pytest.raises(ValueError, match="ride_"):
        register_ride(out, ["seg_meta.json"], ride)
    with pytest.raises(FileNotFoundError):
        register_ride(out, ["ride_missing.json"], ride)


@pytest.mark.unit
def test_walk_summary_reads_headline_from_metrics(source: Path) -> None:
    manifest = json.loads((source / "manifest.json").read_text())

    summary = walk_summary(source, manifest)

    assert summary["exposure"] == "streetlight_pedestrian"
    assert summary["headline"] == {"capture_top10": 0.74}
