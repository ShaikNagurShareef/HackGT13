"""Personal-safety layer of the artifact bundle (optional: older bundles have none).

Crime appears only as per-hex counts and bands for display. Routing receives just
`SafetyBundle.edges` (lighting and foot traffic), never the crime tables.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from app.domain.safety import DAY_PART_KEYS, M_PER_DEG, EdgeSignals

log = logging.getLogger(__name__)
SAFETY_FILES = (
    "safety_meta.json",
    "safety_hexes.json",
    "help_points.json",
    "segment_safety.npy",
    "edge_safety.npy",
)
REF_LAT = 33.7756
KX = M_PER_DEG * float(np.cos(np.radians(REF_LAT)))


@dataclass(frozen=True)
class HelpPoint:
    kind: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class SafetyBundle:
    meta: dict[str, Any]
    cells: tuple[str, ...]
    index: dict[str, int]
    lat: np.ndarray
    lon: np.ndarray
    crimes: dict[str, np.ndarray]  # day part -> reported crimes against persons, 12 months
    crime_band: dict[str, tuple[str, ...]]
    lit_share: tuple[float | None, ...]
    activity_band: dict[str, tuple[str | None, ...]]
    help_counts: np.ndarray
    help_points: tuple[HelpPoint, ...]
    help_lon: np.ndarray
    help_lat: np.ndarray
    help_tree: cKDTree  # local metres
    segments: np.ndarray  # n_segments x (lit, activity x 4, help_dist_m)
    edges: EdgeSignals

    @property
    def data_through(self) -> str:
        return str(self.meta["data_through"])


def to_local_m(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    return np.column_stack([np.asarray(lon) * KX, np.asarray(lat) * M_PER_DEG])


def _help_points(rows: list[dict[str, Any]]) -> tuple[HelpPoint, ...]:
    return tuple(
        HelpPoint(str(r["kind"]), str(r["name"]), float(r["lat"]), float(r["lon"])) for r in rows
    )


def _build(root: Path, n_segments: int, n_edges: int) -> SafetyBundle | None:
    hexes = json.loads((root / "safety_hexes.json").read_text())
    points = _help_points(json.loads((root / "help_points.json").read_text()))
    segments = np.load(root / "segment_safety.npy")
    edge = np.load(root / "edge_safety.npy")
    if segments.shape[0] != n_segments or edge.shape != (n_edges, 1 + len(DAY_PART_KEYS)):
        log.warning("safety files do not match this bundle's graph; safety layer disabled")
        return None
    help_lon = np.array([p.lon for p in points])
    help_lat = np.array([p.lat for p in points])
    return SafetyBundle(
        meta=json.loads((root / "safety_meta.json").read_text()),
        cells=tuple(hexes["cells"]),
        index={c: i for i, c in enumerate(hexes["cells"])},
        lat=np.asarray(hexes["lat"], dtype=float),
        lon=np.asarray(hexes["lon"], dtype=float),
        crimes={k: np.asarray(hexes["crimes"][k], dtype=np.int64) for k in DAY_PART_KEYS},
        crime_band={k: tuple(hexes["crime_band"][k]) for k in DAY_PART_KEYS},
        lit_share=tuple(hexes["lit_share"]),
        activity_band={k: tuple(hexes["activity_band"][k]) for k in DAY_PART_KEYS},
        help_counts=np.asarray(hexes["help_points"], dtype=np.int64),
        help_points=points,
        help_lon=help_lon,
        help_lat=help_lat,
        help_tree=cKDTree(to_local_m(help_lon, help_lat).reshape(-1, 2)),
        segments=segments,
        edges=EdgeSignals(lit=edge[:, 0].copy(), activity=edge[:, 1:].copy()),
    )


def load_safety(root: Path, n_segments: int, n_edges: int) -> SafetyBundle | None:
    """The safety layer, or None when the bundle predates it or its files are unusable.

    File integrity (sha256) is already enforced by load_bundle via the manifest.
    """
    if not all((root / name).exists() for name in SAFETY_FILES):
        return None
    try:
        return _build(root, n_segments, n_edges)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("safety layer unreadable (%s); safety endpoints disabled", exc)
        return None
