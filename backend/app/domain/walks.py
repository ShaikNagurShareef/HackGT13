"""Share my walk: a walker's live position, destination, and ETA for a friend to follow.

Nothing here reads or produces traffic-risk scores, and no crime or demographic data is involved.
A shared walk lives six hours after its last update, then MongoDB's TTL monitor deletes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, get_args

WalkStatus = Literal["walking", "arrived", "ended"]
WALK_STATUSES: frozenset[str] = frozenset(get_args(WalkStatus))

WALK_TTL = timedelta(hours=6)
MIN_UPDATE_INTERVAL = timedelta(seconds=3)
MAX_ROUTE_POINTS = 2000
MAX_ETA_S = 12 * 3600
MAX_LABEL_CHARS = 120

# Generous metro-Atlanta box (min_lon, min_lat, max_lon, max_lat): wider than model coverage so
# a walk that starts or ends just outside it can still be followed.
ATLANTA_BBOX = (-84.85, 33.35, -83.95, 34.25)

Point = tuple[float, float]  # (lon, lat)


def in_atlanta(lat: float, lon: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = ATLANTA_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


@dataclass(frozen=True)
class Destination:
    label: str
    lat: float
    lon: float


@dataclass(frozen=True)
class WalkPosition:
    lat: float
    lon: float
    accuracy_m: float | None
    at: datetime


@dataclass(frozen=True)
class SharedWalk:
    walk_id: str
    token_hash: str  # SHA-256 of the owner token; the token itself is never stored
    status: WalkStatus
    destination: Destination
    eta_at: datetime
    position: WalkPosition | None
    route: tuple[Point, ...] | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
