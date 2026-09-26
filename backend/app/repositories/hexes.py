"""City Pulse hex bundle (optional part of the artifact bundle): citywide area scores."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h3
import numpy as np

from app.domain.timeutil import Cell

HEX_RES = 9
GROUPS = ("arterial", "collector", "local")


@dataclass(frozen=True)
class HexBundle:
    cells: tuple[str, ...]
    index: dict[str, int]
    lat: np.ndarray
    lon: np.ndarray
    share: dict[str, np.ndarray]
    factors: np.ndarray  # n_hex x n_factors (centered log contributions)
    factor_keys: tuple[str, ...]
    labels: dict[str, str]
    temporal_key: str
    base: float
    quantiles: np.ndarray
    multipliers: dict[tuple[str, str, int, str, bool], float]
    crashes: np.ndarray
    ped_crashes: np.ndarray
    confidence: tuple[str, ...]
    metrics: dict[str, Any]

    def cell_for(self, lat: float, lon: float) -> str | None:
        cell = h3.latlng_to_cell(lat, lon, HEX_RES)
        return cell if cell in self.index else None

    def temporal_log(self, i: int, cell: Cell) -> float:
        mix = sum(float(self.share[g][i]) * self.multipliers[(g, *cell.key)] for g in GROUPS)
        return float(np.log(max(mix, 1e-12)))


def load_hexes(root: Path) -> HexBundle | None:
    meta_path = root / "hex_meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    m = meta["multipliers"]
    multipliers = {
        (rg, dg, int(h), lt, bool(w)): float(v)
        for rg, dg, h, lt, w, v in zip(
            m["road_group"], m["day_group"], m["hour"], m["light"], m["wet"], m["mult"], strict=True
        )
    }
    keys = tuple(f["key"] for f in meta["factors"])
    labels = {f["key"]: f["label"] for f in meta["factors"]}
    labels[meta["temporal"]["key"]] = meta["temporal"]["label"]
    return HexBundle(
        cells=tuple(meta["cells"]),
        index={c: i for i, c in enumerate(meta["cells"])},
        lat=np.asarray(meta["lat"]),
        lon=np.asarray(meta["lon"]),
        share={g: np.asarray(meta["share"][g]) for g in GROUPS},
        factors=np.load(root / "hex_factors.npy").astype(np.float64),
        factor_keys=keys,
        labels=labels,
        temporal_key=meta["temporal"]["key"],
        base=float(meta["base"]),
        quantiles=np.asarray(meta["quantiles"], dtype=float),
        multipliers=multipliers,
        crashes=np.asarray(meta["crashes"]),
        ped_crashes=np.asarray(meta["ped_crashes"]),
        confidence=tuple(meta["confidence"]),
        metrics=meta.get("metrics", {}),
    )
