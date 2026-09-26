"""Group model contributions into plain-language factors (PRD EXP-01, §7.4 copy rules).

log density(seg, cell) = base + sum(spatial factors[seg]) + sum(temporal factors[cell]),
with every factor centered at its mean so the base is "a typical street at a typical hour".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SPATIAL_FACTORS: dict[str, str] = {
    "history": "Pedestrian crash history here",
    "nearby_history": "Pedestrian crashes on nearby streets",
    "vehicle_crashes": "Vehicle crashes on this street",
    "traffic_volume": "Traffic volume",
    "speed": "Speed limit",
    "lanes": "Number of lanes",
    "road_type": "Road type",
    "ped_activity": "Pedestrian activity",
    "destinations": "Restaurants and nightlife nearby",
    "transit": "Transit stops",
    "intersection": "Intersection complexity",
    "sidewalk": "Sidewalk condition",
    "school": "School zone",
    "lighting": "Mapped street lighting",
    "length": "Block length",
}
TEMPORAL_FACTORS: dict[str, str] = {
    "time_of_day": "Time of day",
    "day_of_week": "Day of week",
    "light": "Darkness",
    "rain": "Wet pavement",
}
FEATURE_TO_FACTOR: dict[str, str] = {
    "log_aadt": "traffic_volume",
    "aadt_missing": "traffic_volume",
    "arc_aadt_risk": "traffic_volume",
    "speed": "speed",
    "arc_psl_risk": "speed",
    "lanes": "lanes",
    "arc_lanes_risk": "lanes",
    "group_arterial": "road_type",
    "group_collector": "road_type",
    "group_local": "road_type",
    "is_service": "road_type",
    "oneway": "road_type",
    "state_owned": "road_type",
    "arc_gdot_risk": "road_type",
    "arc_min_art_risk": "road_type",
    "arc_urban_risk": "road_type",
    "arc_high_dev_risk": "road_type",
    "arc_structural_count": "road_type",
    "log_ped_volume": "ped_activity",
    "ped_volume_missing": "ped_activity",
    "log_food_n": "destinations",
    "log_nightlife_n": "destinations",
    "bus_stops_n": "transit",
    "log_bus_boardings": "transit",
    "arc_bus_risk": "transit",
    "arc_high_bus_risk": "transit",
    "log_rail_dist": "transit",
    "node_degree_max": "intersection",
    "signals_n": "intersection",
    "crossings_n": "intersection",
    "sidewalk_n": "sidewalk",
    "sidewalk_cond": "sidewalk",
    "school_zone": "school",
    "osm_lit": "lighting",
    "log_nonped_density": "vehicle_crashes",
    "log_nbr_nonped_density": "vehicle_crashes",
    "log_nbr_ped_density": "nearby_history",
    "log_len": "length",
}


@dataclass(frozen=True)
class Decomposition:
    base: float
    spatial: pd.DataFrame  # segments x SPATIAL_FACTORS (centered)
    temporal: pd.DataFrame  # cells x TEMPORAL_FACTORS (centered)


def decompose(
    spf_contrib: pd.DataFrame,
    spf_base: float,
    eb_log_adjust: np.ndarray,
    log_len_per_100m: np.ndarray,
    road_base: np.ndarray,
    temporal: pd.DataFrame,
) -> Decomposition:
    """Assemble centered factors; see module docstring for the identity maintained."""
    spatial = pd.DataFrame(0.0, index=spf_contrib.index, columns=list(SPATIAL_FACTORS))
    for feature in spf_contrib.columns:
        spatial[FEATURE_TO_FACTOR[feature]] += spf_contrib[feature].to_numpy()
    spatial["history"] += eb_log_adjust
    spatial["length"] -= log_len_per_100m  # density per 100 m
    spatial["road_type"] += road_base  # temporal model's road-group level
    temporal = temporal.loc[:, list(TEMPORAL_FACTORS)]
    s_mean, t_mean = spatial.mean(), temporal.mean()
    base = spf_base + float(s_mean.sum()) + float(t_mean.sum())
    return Decomposition(base=base, spatial=spatial - s_mean, temporal=temporal - t_mean)
