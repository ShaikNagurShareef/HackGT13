"""Add the personal-safety files to a tiny test bundle (see bundle_factory.py for the grid).

Signals (night): the calm top row is unlit and quiet, the bottom row is lit and busy, the
hot middle row and the cross streets are unknown. Crimes sit in the hex of the middle row.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import h3
import numpy as np

from tests.bundle_factory import COLS, DLAT, DLON, LAT0, LON0, ROWS

LIT, UNLIT, UNKNOWN = 1, 0, -1
QUIET, BUSY = 0, 2
DAY_PARTS = [
    {"key": "night", "label": "Night (10 PM to 6 AM)", "hours": [22, 23, 0, 1, 2, 3, 4, 5]},
    {"key": "morning", "label": "Morning (6 AM to 12 PM)", "hours": list(range(6, 12))},
    {"key": "afternoon", "label": "Afternoon (12 PM to 6 PM)", "hours": list(range(12, 18))},
    {"key": "evening", "label": "Evening (6 PM to 10 PM)", "hours": list(range(18, 22))},
]
KEYS = [p["key"] for p in DAY_PARTS]
SAFETY_FILES = (
    "safety_meta.json",
    "safety_hexes.json",
    "help_points.json",
    "segment_safety.npy",
    "edge_safety.npy",
)
HOT_CRIMES = 7


def _row_signals(row: int) -> tuple[int, int]:
    if row == 0:
        return UNLIT, QUIET
    if row == ROWS - 1:
        return LIT, BUSY
    return UNKNOWN, UNKNOWN


def edge_rows() -> list[int]:
    """Row of each edge in bundle_factory order (horizontal edges first; vertical = -1)."""
    horizontal = [r for r in range(ROWS) for _ in range(COLS - 1)]
    return horizontal + [-1] * ((ROWS - 1) * COLS)


def grid_cells() -> list[str]:
    lats = [LAT0 + r * DLAT for r in range(ROWS)]
    lons = [LON0 + c * DLON / 2 for c in range(2 * COLS - 1)]
    return sorted({h3.latlng_to_cell(la, lo, 9) for la in lats for lo in lons})


def write_safety(root: Path, crimes_scale: int = 1, lit: dict[int, int] | None = None) -> None:
    """Write the five safety files into `root` and register them in its manifest."""
    rows = edge_rows()
    signals = np.array([_row_signals(r) for r in rows])
    lit_codes = signals[:, 0] if lit is None else np.array([lit.get(r, UNKNOWN) for r in rows])
    edge = np.column_stack([lit_codes, np.repeat(signals[:, 1:2], len(KEYS), axis=1)])
    np.save(root / "edge_safety.npy", edge.astype(np.int8))
    seg = np.column_stack([edge, np.full(len(rows), 80)]).astype(np.int16)
    np.save(root / "segment_safety.npy", seg)
    cells = grid_cells()
    hot = h3.latlng_to_cell(LAT0 + DLAT, LON0 + DLON, 9)
    crimes = [HOT_CRIMES * crimes_scale if c == hot else 0 for c in cells]
    latlng = [h3.cell_to_latlng(c) for c in cells]
    _write(
        root / "safety_hexes.json",
        {
            "cells": cells,
            "lat": [p[0] for p in latlng],
            "lon": [p[1] for p in latlng],
            "crimes": {k: crimes for k in KEYS},
            "crime_band": {k: ["higher" if n else "typical" for n in crimes] for k in KEYS},
            "lit_share": [0.5 if i == 0 else None for i in range(len(cells))],
            "activity_band": {k: ["busy"] + [None] * (len(cells) - 1) for k in KEYS},
            "help_points": [1] + [0] * (len(cells) - 1),
        },
    )
    center_lat, center_lon = LAT0 + DLAT, LON0 + DLON  # the middle node of the grid
    _write(
        root / "help_points.json",
        [
            {"kind": "police", "name": "Police station", "lat": center_lat, "lon": center_lon},
            {"kind": "blue_light", "name": "Ferst and Fowler", "lat": LAT0, "lon": LON0},
            {"kind": "hospital", "name": "Far away", "lat": LAT0 + 0.05, "lon": LON0},
        ],
    )
    _write(
        root / "safety_meta.json",
        {
            "data_through": "2026-09-26",
            "sources": [
                {"name": "APD open data", "url": "https://example.org", "license": "Public"}
            ],
            "crime_categories": ["Aggravated assault", "Homicide", "Robbery", "Simple assault"],
            "day_parts": DAY_PARTS,
        },
    )
    manifest = json.loads((root / "manifest.json").read_text())
    for name in SAFETY_FILES:
        manifest["files"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    _write(root / "manifest.json", manifest)


def _write(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj))
