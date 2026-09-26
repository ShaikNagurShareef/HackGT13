"""Add the ride model to a NEW bundle version without touching a single walk byte.

The new version starts as a byte-for-byte copy of the source bundle; ride files are written
only under the `ride_` prefix and registered in the manifest with their sha256.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RIDE_PREFIX = "ride_"
MANIFEST = "manifest.json"
WALK_MODEL_FILES: tuple[str, ...] = (
    "segments.geojson",
    "seg_meta.json",
    "factors.json",
    "spatial_factors.npy",
    "walk_graph.npz",
    "hotspot_nodes.json",
    "metrics.json",
)
_WALK_FRAMES = re.compile(r"^frames_[a-z]+_[a-z]+\.bin$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest(root: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((root / MANIFEST).read_text())
    return manifest


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / MANIFEST).write_text(json.dumps(manifest, separators=(",", ":")))


def ride_name(walk_file: str) -> str:
    """Ride mirror of a walk-model file name (`walk_graph.npz` -> `ride_graph.npz`)."""
    if walk_file == "walk_graph.npz":
        return f"{RIDE_PREFIX}graph.npz"
    return f"{RIDE_PREFIX}{walk_file}"


def walk_files(manifest: dict[str, Any]) -> list[str]:
    """Walk-model outputs listed in a manifest (not City Pulse or personal-safety layers)."""
    names = manifest.get("files", {})
    return sorted(n for n in names if n in WALK_MODEL_FILES or _WALK_FRAMES.match(n))


def new_ride_version(source: Path, version: str) -> Path:
    """Copy `source` to a sibling `version` directory and stamp the new manifest."""
    out = source.parent / version
    if out.exists():
        raise FileExistsError(f"bundle version already exists: {out}")
    shutil.copytree(source, out)
    manifest = _read_manifest(out)
    stamped = {
        **manifest,
        "model_version": version,
        "derived_from": source.name,
        "ride_added_at": datetime.now(UTC).isoformat(),
    }
    _write_manifest(out, stamped)
    return out


def verify_unchanged(source: Path, out: Path) -> list[str]:
    """Names of files in `source` (other than the manifest) whose bytes differ in `out`."""
    return sorted(
        p.name
        for p in source.iterdir()
        if p.is_file()
        and p.name != MANIFEST
        and (not (out / p.name).exists() or _sha256(out / p.name) != _sha256(p))
    )


def walk_summary(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    metrics = json.loads((root / "metrics.json").read_text())
    return {
        "files": walk_files(manifest),
        "model": "pedestrian crashes",
        "headline": metrics.get("headline", {}),
        "exposure": "streetlight_pedestrian",
    }


def register_ride(
    out: Path,
    files: list[str],
    ride: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record each ride file's sha256 and the per-mode summary in `out`'s manifest."""
    unprefixed = [f for f in files if not f.startswith(RIDE_PREFIX)]
    if unprefixed:
        raise ValueError(f"ride file names must start with {RIDE_PREFIX!r}: {unprefixed}")
    missing = [f for f in files if not (out / f).is_file()]
    if missing:
        raise FileNotFoundError(f"ride files not written: {missing}")
    manifest = _read_manifest(out)
    hashes = {**manifest.get("files", {}), **{f: _sha256(out / f) for f in files}}
    modes = {
        "walk": walk_summary(out, manifest),
        "ride": {"files": sorted(files), **ride},
    }
    updated = {**manifest, **(extra or {}), "files": hashes, "modes": modes}
    _write_manifest(out, updated)
    return updated
