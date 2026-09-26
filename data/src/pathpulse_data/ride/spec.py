"""Ride-mode factor keys and labels (PRD copy rules: say "traffic risk", never "safe")."""

from __future__ import annotations

from pathpulse_data.export.factors import FEATURE_TO_FACTOR, TEMPORAL_FACTORS, FactorSpec

RIDE_SPATIAL_FACTORS: dict[str, str] = {
    "history": "Cyclist crash history here",
    "nearby_history": "Cyclist crashes on nearby streets",
    "vehicle_crashes": "Other crashes on this street",
    "traffic_volume": "Traffic volume",
    "speed": "Speed limit",
    "lanes": "Number of lanes",
    "road_type": "Road type",
    "bike_facility": "Bike facility on this street",
    "bike_activity": "Cycling activity (Strava proxy)",
    "ped_activity": "Pedestrian activity",
    "destinations": "Restaurants and nightlife nearby",
    "transit": "Transit stops",
    "intersection": "Intersection complexity",
    "sidewalk": "Sidewalk condition",
    "school": "School zone",
    "lighting": "Mapped street lighting",
    "length": "Block length",
}
RIDE_FEATURE_TO_FACTOR: dict[str, str] = {
    **FEATURE_TO_FACTOR,
    "bike_protected": "bike_facility",
    "bike_painted": "bike_facility",
    "bike_shared": "bike_facility",
    "beltline_adjacent": "bike_facility",
    "log_bike_activity": "bike_activity",
}
RIDE_SPEC = FactorSpec(RIDE_SPATIAL_FACTORS, dict(TEMPORAL_FACTORS), RIDE_FEATURE_TO_FACTOR)
_POOLED_LABELS = {
    "history": "Pedestrian and cyclist crash history here",
    "nearby_history": "Pedestrian and cyclist crashes on nearby streets",
}


def ride_spec(pooled: bool) -> FactorSpec:
    """Ride factors; a model trained on pooled pedestrian+cyclist crashes says so."""
    if not pooled:
        return RIDE_SPEC
    return FactorSpec(
        {**RIDE_SPATIAL_FACTORS, **_POOLED_LABELS}, dict(TEMPORAL_FACTORS), RIDE_FEATURE_TO_FACTOR
    )
