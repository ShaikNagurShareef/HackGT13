"""MARTA heavy-rail stations for the transit hand-off ("take MARTA for part of it").

The committed list (all 38 rail stations, with lines) is complete; the bundle's help points
only carry the stations near the safety layer, so the static list is the source here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

STATIONS_FILE = Path(__file__).with_name("marta_stations.json")


@dataclass(frozen=True)
class RailStation:
    name: str
    lat: float
    lon: float
    lines: tuple[str, ...]


@cache
def load_rail_stations(path: Path = STATIONS_FILE) -> tuple[RailStation, ...]:
    rows = json.loads(path.read_text())
    return tuple(
        RailStation(str(r["name"]), float(r["lat"]), float(r["lon"]), tuple(r.get("lines", [])))
        for r in rows
    )


def stations_in_bbox(
    stations: tuple[RailStation, ...], bbox: list[float]
) -> tuple[RailStation, ...]:
    west, south, east, north = bbox
    return tuple(s for s in stations if west <= s.lon <= east and south <= s.lat <= north)
