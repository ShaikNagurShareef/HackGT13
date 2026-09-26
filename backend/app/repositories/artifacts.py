"""Load and validate the exported model bundle (artifacts/<model_version>/).

The bundle is the demo's hot path: everything the API needs is in memory after startup,
and nothing here touches the database (PRD NFR-04, EC-36).

One bundle directory holds one model per travel network, loaded through the same code path:
the walk model under bare file names and the ride model (bike / e-bike / scooter) under a
`ride_` prefix that mirrors every walk file (`ride_graph.npz` mirrors `walk_graph.npz`).
The ride model is optional: missing or corrupt ride files disable riding, never walking.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import numpy as np

from app.domain.timeutil import Cell

log = logging.getLogger(__name__)

WALK_PREFIX, RIDE_PREFIX = "", "ride_"
REQUIRED_FILES = (
    "manifest.json",
    "seg_meta.json",
    "factors.json",
    "spatial_factors.npy",
    "walk_graph.npz",
    "hotspot_nodes.json",
    "metrics.json",
)
# Model files every mode needs, by their walk name; other modes prefix them.
MODE_FILES = ("seg_meta.json", "factors.json", "spatial_factors.npy")


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
    prefix: str = WALK_PREFIX  # "" for the walk model, "ride_" for the ride model

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


def graph_file(prefix: str) -> str:
    return "walk_graph.npz" if prefix == WALK_PREFIX else f"{prefix}graph.npz"


def _required(prefix: str) -> tuple[str, ...]:
    if prefix == WALK_PREFIX:
        return REQUIRED_FILES
    return ("manifest.json", graph_file(prefix), *(f"{prefix}{f}" for f in MODE_FILES))


def _owned(name: str, prefix: str) -> bool:
    """Walk verifies every non-ride file (as before); a prefixed mode verifies its own files."""
    if prefix == WALK_PREFIX:
        return not name.startswith(RIDE_PREFIX)
    return name.startswith(prefix)


def _verify(root: Path, manifest: dict[str, Any], prefix: str) -> None:
    missing = [f for f in _required(prefix) if not (root / f).exists()]
    if missing:
        raise BundleError(f"bundle {root} missing files: {missing}")
    for name, expected in manifest.get("files", {}).items():
        if not _owned(name, prefix):
            continue
        path = root / name
        if not path.exists() or _sha256(path) != expected:
            raise BundleError(f"bundle file {name} failed its sha256 check")


def _optional_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def _metrics(root: Path, manifest: dict[str, Any], prefix: str) -> dict[str, Any]:
    if prefix == WALK_PREFIX:
        return dict(json.loads((root / "metrics.json").read_text()))
    fallback = {"headline": manifest.get("modes", {}).get("ride", {}).get("headline", {})}
    return dict(_optional_json(root / f"{prefix}metrics.json", fallback))


def _load_graph(path: Path) -> WalkGraph:
    with np.load(path) as npz:
        return WalkGraph(**{f.name: npz[f.name] for f in fields(WalkGraph)})


def _check_shapes(bundle: Bundle) -> None:
    """Segment ids in the graph and metadata must index the factor matrix."""
    n = bundle.n_segments
    seg = bundle.graph.edge_seg
    if len(bundle.seg_meta["name"]) != n or (len(seg) and int(seg.max()) >= n):
        raise BundleError(f"bundle {bundle.prefix or 'walk'} model has mismatched segment ids")


def load_bundle(root: Path, prefix: str = WALK_PREFIX) -> Bundle:
    root = root.resolve()
    if not (root / "manifest.json").exists():
        raise BundleError(f"no manifest at {root}")
    manifest = json.loads((root / "manifest.json").read_text())
    _verify(root, manifest, prefix)
    factors = json.loads((root / f"{prefix}factors.json").read_text())
    spatial = np.load(root / f"{prefix}spatial_factors.npy").astype(np.float64)
    temporal = {
        (r["day_group"], int(r["hour"]), r["light"], bool(r["wet"])): np.asarray(r["values"])
        for r in factors["temporal_rows"]
    }
    bundle = Bundle(
        root=root,
        manifest=manifest,
        seg_meta=json.loads((root / f"{prefix}seg_meta.json").read_text()),
        base=float(factors["base"]),
        quantiles=np.asarray(factors["quantiles"], dtype=float),
        spatial_keys=tuple(f["key"] for f in factors["spatial"]),
        spatial_labels={f["key"]: f["label"] for f in factors["spatial"]},
        spatial=spatial,
        temporal_keys=tuple(f["key"] for f in factors["temporal"]),
        temporal_labels={f["key"]: f["label"] for f in factors["temporal"]},
        temporal=temporal,
        graph=_load_graph(root / graph_file(prefix)),
        hotspot_nodes=_optional_json(root / f"{prefix}hotspot_nodes.json", []),
        metrics=_metrics(root, manifest, prefix),
        spatial_sum=spatial.sum(axis=1),
        prefix=prefix,
    )
    _check_shapes(bundle)
    return bundle


def load_ride_bundle(root: Path) -> Bundle | None:
    """The ride model, or None when its files are absent or unusable (walk is unaffected)."""
    if not (root / graph_file(RIDE_PREFIX)).exists():
        return None
    try:
        return load_bundle(root, prefix=RIDE_PREFIX)
    except (BundleError, OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        log.warning("ride model unavailable: %s", exc)
        return None
