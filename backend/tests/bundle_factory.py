"""Write a tiny, valid artifact bundle for tests.

World: a 3-column x 3-row walk grid near Georgia Tech. Columns are ~200 m apart and rows
~40 m apart. The middle row is a hot corridor; the top row is calm. Walking middle-left to
middle-right: fastest = middle row (400 m); lower-risk = up, across the top, down (480 m,
inside the 1.25x detour budget).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

LAT0, LON0 = 33.7760, -84.3960
DLAT = 40 / 111_320  # ~40 m per row
DLON = 200 / (111_320 * math.cos(math.radians(LAT0)))  # ~200 m per column
ROWS, COLS = 3, 3
HOT_ROW, CALM_ROW = 1, 0
SPATIAL_KEYS = ("history", "traffic_volume", "speed")
TEMPORAL_KEYS = ("time_of_day", "day_of_week", "light", "rain")
MODEL_VERSION = "pp-test-0001"


def node_id(row: int, col: int) -> int:
    return row * COLS + col


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _edges() -> list[tuple[int, int, int]]:
    """(u, v, row_of_edge) for horizontal edges; vertical edges carry row -1."""
    out = []
    for r, c in itertools.product(range(ROWS), range(COLS - 1)):
        out.append((node_id(r, c), node_id(r, c + 1), r))
    for r, c in itertools.product(range(ROWS - 1), range(COLS)):
        out.append((node_id(r, c), node_id(r + 1, c), -1))
    return out


def write_bundle(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lats = np.array([LAT0 + r * DLAT for r in range(ROWS) for _ in range(COLS)])
    lons = np.array([LON0 + c * DLON for _ in range(ROWS) for c in range(COLS)])
    edges = _edges()
    n_seg = len(edges)
    risk = {HOT_ROW: 2.0, CALM_ROW: -2.0, 2: 0.0, -1: -1.0}
    spatial = np.array([[risk[row], 0.1 * i / n_seg, 0.0] for i, (_, _, row) in enumerate(edges)])
    coords, offsets = [], [0]
    for u, v, _ in edges:
        coords += [[lons[u], lats[u]], [lons[v], lats[v]]]
        offsets.append(len(coords))
    lengths = [_haversine_m(lats[u], lons[u], lats[v], lons[v]) for u, v, _ in edges]
    np.savez_compressed(
        root / "walk_graph.npz",
        node_lon=lons,
        node_lat=lats,
        edge_u=np.array([e[0] for e in edges], np.int32),
        edge_v=np.array([e[1] for e in edges], np.int32),
        edge_len=np.array(lengths, np.float32),
        edge_seg=np.arange(n_seg, dtype=np.int32),
        edge_kind=np.zeros(n_seg, np.uint8),
        coords=np.array(coords),
        coord_offsets=np.array(offsets, np.int32),
    )
    np.save(root / "spatial_factors.npy", spatial.astype(np.float32))
    rows = [
        {
            "day_group": dg,
            "hour": h,
            "light": lt,
            "wet": wet,
            "values": [
                0.3 if lt == "dark" else 0.0,
                0.0,
                0.2 if lt == "dark" else 0.0,
                0.1 if wet else 0.0,
            ],
        }
        for dg in ("weekday", "friday", "saturday", "sunday")
        for h in range(24)
        for lt in ("day", "twilight", "dark")
        for wet in (False, True)
    ]
    _write_json(
        root / "factors.json",
        {
            "base": -1.0,
            "spatial": [{"key": k, "label": k.replace("_", " ").title()} for k in SPATIAL_KEYS],
            "temporal": [{"key": k, "label": k.replace("_", " ").title()} for k in TEMPORAL_KEYS],
            "temporal_rows": rows,
            "quantiles": np.linspace(-5.0, 3.0, 1001).tolist(),
        },
    )
    names = [f"Row {row} St" if row >= 0 else "Cross Ave" for _, _, row in edges]
    _write_json(
        root / "seg_meta.json",
        {
            "name": names,
            "road_group": ["arterial"] * n_seg,
            "length_m": lengths,
            "eb": [0.5] * n_seg,
            "spf": [0.4] * n_seg,
            "crashes": [12.0] * n_seg,
            "ped_crashes": [2.0 if row == HOT_ROW else 0.0 for _, _, row in edges],
            "dark_share": [0.4] * n_seg,
            "wet_share": [0.1] * n_seg,
            "confidence": ["high" if row == HOT_ROW else "limited" for _, _, row in edges],
        },
    )
    _write_json(root / "hotspot_nodes.json", [[lons[4], lats[4], [2, 3]]])
    _write_json(root / "metrics.json", {"headline": {"capture_top10": 0.47, "roc_auc": 0.87}})
    (root / "frames_weekday_dry.bin").write_bytes(bytes(24 * n_seg))
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir())}
    _write_json(
        root / "manifest.json",
        {
            "model_version": MODEL_VERSION,
            "data_through": "2026-09-19",
            "n_segments": n_seg,
            "day_groups": ["weekday", "friday", "saturday", "sunday"],
            "conditions": ["dry", "wet"],
            "coverage_bbox": [-84.415, 33.745, -84.370, 33.795],
            "reference_dates": {"weekday": "2026-09-28"},
            "frame_light": {},
            "files": files,
        },
    )
    return root


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj))
