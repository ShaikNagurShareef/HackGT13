"""Personal-safety queries: hexes and help points in view, and signals along a route.

Reported crimes are counted for display only; nothing here feeds routing or risk scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import h3
import numpy as np

from app.api.schemas import RouteSafetyOut
from app.domain.route_metrics import RouteMetrics
from app.domain.safety import (
    LIT,
    busier_share,
    day_part_at,
    day_part_for_hour,
    densify,
    known_share,
)
from app.repositories.safety import HelpPoint, SafetyBundle, to_local_m

MAX_HEXES = 4000  # the whole city is ~3,540 hexes; a 0.3 degree view never exceeds this
MAX_HELP_POINTS = 1000
BBOX_PAD_DEG = 0.003  # ~half a res-9 hex, so hexes straddling the view edge are kept
HEX_RES = 9
CORRIDOR_STEP_M = 20.0
HELP_RADIUS_M = 100.0
SHARE_DECIMALS = 3

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class HexRow:
    h3: str
    lat: float
    lon: float
    crimes_persons_12mo: int
    crime_band: str
    lit_share: float | None
    activity_band: str | None
    help_points: int


def _inside(lon: np.ndarray, lat: np.ndarray, bbox: BBox, pad: float = 0.0) -> np.ndarray:
    west, south, east, north = bbox
    return (lon >= west - pad) & (lon <= east + pad) & (lat >= south - pad) & (lat <= north + pad)


def hexes_in_bbox(safety: SafetyBundle, bbox: BBox, hour: int) -> list[HexRow]:
    part = day_part_for_hour(hour)
    idx = np.flatnonzero(_inside(safety.lon, safety.lat, bbox, BBOX_PAD_DEG))[:MAX_HEXES]
    return [
        HexRow(
            h3=safety.cells[i],
            lat=float(safety.lat[i]),
            lon=float(safety.lon[i]),
            crimes_persons_12mo=int(safety.crimes[part][i]),
            crime_band=safety.crime_band[part][i],
            lit_share=safety.lit_share[i],
            activity_band=safety.activity_band[part][i],
            help_points=int(safety.help_counts[i]),
        )
        for i in idx
    ]


def help_points_in_bbox(safety: SafetyBundle, bbox: BBox) -> list[HelpPoint]:
    idx = np.flatnonzero(_inside(safety.help_lon, safety.help_lat, bbox))[:MAX_HELP_POINTS]
    return [safety.help_points[i] for i in idx]


def _help_points_near(safety: SafetyBundle, pts: np.ndarray) -> int:
    if not safety.help_points or len(pts) == 0:
        return 0
    hits = safety.help_tree.query_ball_point(to_local_m(pts[:, 0], pts[:, 1]), r=HELP_RADIUS_M)
    return len({i for group in hits for i in group})


def _crimes_on_route(safety: SafetyBundle, pts: np.ndarray, part: str) -> int:
    cells = {h3.latlng_to_cell(float(lat), float(lon), HEX_RES) for lon, lat in pts}
    counts = safety.crimes[part]
    return int(sum(counts[safety.index[c]] for c in cells if c in safety.index))


def _round(share: float | None) -> float | None:
    return None if share is None else round(share, SHARE_DECIMALS)


def route_safety(safety: SafetyBundle, route: RouteMetrics, depart: datetime) -> RouteSafetyOut:
    """Lit and busier (moderate or busy) shares by length, help points within 100 m, and
    reported crimes against persons in the hexes the route crosses (display only)."""
    part = day_part_at(depart)
    edges = np.array([s.edge for s in route.edges], dtype=np.int64)
    lengths = np.array([s.length_m for s in route.edges], dtype=float)
    pts = densify(route.coords, CORRIDOR_STEP_M)
    return RouteSafetyOut(
        lit_share=_round(known_share(lengths, safety.edges.lit[edges], LIT)),
        busy_share=_round(busier_share(lengths, safety.edges.activity_for(part)[edges])),
        help_points_within_100m=_help_points_near(safety, pts),
        crimes_persons_nearby=_crimes_on_route(safety, pts, part),
        day_part=part,
    )
