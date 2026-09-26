"""Load and validate the exported model bundle (artifacts/<model_version>/).

The bundle is the demo's hot path: everything the API needs is in memory after startup,
and nothing here touches the database (PRD NFR-04, EC-36).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.domain.timeutil import Cell

REQUIRED_FILES = (
    "manifest.json",
    "seg_meta.json",
    "factors.json",
    "spatial_factors.npy",
    "walk_graph.npz",
    "hotspot_nodes.json",
    "metrics.json",
)


class BundleError(RuntimeError):
    """The artifact bundle is missing, incomplete, or corrupted."""


@dataclass(frozen=True)
class WalkGraph:
    node_lon: np.ndarray
    node_lat: np.ndarray
    edge_u: np.ndarray
    edge_v: np.ndarray
    edge_len: np.ndarray
    edge_seg: np.ndarray
    edge_kind: np.ndarray
    coords: np.ndarray
    coord_offsets: np.ndarray

    def edge_coords(self, edge: int) -> np.ndarray:
        return self.coords[self.coord_offsets[edge] : self.coord_offsets[edge + 1]]


@dataclass(frozen=True)
class Bundle:
    root: Path
    manifest: dict[str, Any]
    seg_meta: dict[str, list[Any]]
    base: float
    quantiles: np.ndarray
    spatial_keys: tuple[str, ...]
    spatial_labels: dict[str, str]
    spatial: np.ndarray  # n_segments x n_spatial_factors
    temporal_keys: tuple[str, ...]
    temporal_labels: dict[str, str]
    temporal: dict[tuple[str, int, str, bool], np.ndarray]
    graph: WalkGraph
    hotspot_nodes: list[list[Any]]
    metrics: dict[str, Any]
    spatial_sum: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))

    @property
    def model_version(self) -> str:
        return str(self.manifest["model_version"])

    @property
    def n_segments(self) -> int:
        return int(self.spatial.shape[0])

    def temporal_sum(self, cell: Cell) -> float:
        return float(self.temporal[cell.key].sum())

    def log_density(self, seg_ids: np.ndarray, cell: Cell) -> np.ndarray:
        return self.base + self.spatial_sum[seg_ids] + self.temporal_sum(cell)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify(root: Path, manifest: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FILES if not (root / f).exists()]
    if missing:
        raise BundleError(f"bundle {root} missing files: {missing}")
    for name, expected in manifest.get("files", {}).items():
        path = root / name
        if not path.exists() or _sha256(path) != expected:
            raise BundleError(f"bundle file {name} failed its sha256 check")


def load_bundle(root: Path) -> Bundle:
    root = root.resolve()
    if not (root / "manifest.json").exists():
        raise BundleError(f"no manifest at {root}")
    manifest = json.loads((root / "manifest.json").read_text())
    _verify(root, manifest)
    factors = json.loads((root / "factors.json").read_text())
    spatial = np.load(root / "spatial_factors.npy").astype(np.float64)
    temporal = {
        (r["day_group"], int(r["hour"]), r["light"], bool(r["wet"])): np.asarray(r["values"])
        for r in factors["temporal_rows"]
    }
    with np.load(root / "walk_graph.npz") as npz:
        graph = WalkGraph(**{k: npz[k] for k in npz.files})
    return Bundle(
        root=root,
        manifest=manifest,
        seg_meta=json.loads((root / "seg_meta.json").read_text()),
        base=float(factors["base"]),
        quantiles=np.asarray(factors["quantiles"], dtype=float),
        spatial_keys=tuple(f["key"] for f in factors["spatial"]),
        spatial_labels={f["key"]: f["label"] for f in factors["spatial"]},
        spatial=spatial,
        temporal_keys=tuple(f["key"] for f in factors["temporal"]),
        temporal_labels={f["key"]: f["label"] for f in factors["temporal"]},
        temporal=temporal,
        graph=graph,
        hotspot_nodes=json.loads((root / "hotspot_nodes.json").read_text()),
        metrics=json.loads((root / "metrics.json").read_text()),
        spatial_sum=spatial.sum(axis=1),
    )
