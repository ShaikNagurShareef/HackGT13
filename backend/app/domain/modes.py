"""Travel modes: walking on the pedestrian network, riding (bike / e-bike / scooter) on the ride
network. A mode picks the model bundle (by file prefix) and the speed the router plans with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.router import LONG_TRIP_S, WALKING, TravelProfile
from app.repositories.artifacts import RIDE_PREFIX, WALK_PREFIX

ModeKey = Literal["walk", "bike", "ebike", "scooter"]
Network = Literal["walk", "ride"]
KMH_PER_MPS = 3.6
RIDE_LONG_TRIP_M = 15_000.0  # past this, suggest MARTA for part of the ride

__all__ = ["MODES", "RIDE_PREFIX", "WALK_PREFIX", "ModeKey", "Network", "TravelMode", "mode_for"]


@dataclass(frozen=True)
class TravelMode:
    key: ModeKey
    label: str
    speed_kmh: float
    network: Network

    @property
    def speed_mps(self) -> float:
        return self.speed_kmh / KMH_PER_MPS

    @property
    def static_prefix(self) -> str:
        return WALK_PREFIX if self.network == "walk" else RIDE_PREFIX

    @property
    def is_ride(self) -> bool:
        return self.network == "ride"

    @property
    def profile(self) -> TravelProfile:
        if not self.is_ride:
            return WALKING
        return TravelProfile(self.speed_mps, RIDE_LONG_TRIP_M, LONG_TRIP_S)


MODES: dict[str, TravelMode] = {
    "walk": TravelMode("walk", "Walk", WALKING.speed_mps * KMH_PER_MPS, "walk"),
    "bike": TravelMode("bike", "Bike", 15.0, "ride"),
    "ebike": TravelMode("ebike", "E-bike", 22.0, "ride"),
    "scooter": TravelMode("scooter", "Scooter", 18.0, "ride"),
}


def mode_for(key: str) -> TravelMode:
    return MODES[key]
