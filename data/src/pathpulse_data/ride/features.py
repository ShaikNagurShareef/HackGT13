"""Ride features per road segment: bike facility class, BeltLine adjacency, cycling activity.

Geometries must share a projected CRS in meters. No demographic, income, or crime inputs.
"""

from __future__ import annotations

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import shapely

from pathpulse_data.network.bike import BikeInfra
from pathpulse_data.network.conflate import conflate_lines

RIDE_EXTRA_COLUMNS: tuple[str, ...] = (
    "bike_protected",
    "bike_painted",
    "bike_shared",
    "beltline_adjacent",
    "log_bike_activity",
)
FACILITY_MATCH_M = 20.0  # a bike lane or sidepath is drawn within ~20 m of the centerline
FACILITY_ANGLE_DEG = 30.0  # ...and runs along it (a crossing path is not the street's facility)
BELTLINE_RADIUS_M = 15.0
STRAVA_H3_RES = 8  # ARC publishes Strava Metro counts on H3 res-8 hexes


def facility_by_segment(
    segs: gpd.GeoDataFrame,
    sources: list[gpd.GeoDataFrame],
    max_m: float = FACILITY_MATCH_M,
    max_angle_deg: float = FACILITY_ANGLE_DEG,
) -> pd.Series:
    """Strongest BikeInfra class among parallel facility lines (column `infra`) per segment."""
    best = np.full(len(segs), int(BikeInfra.NONE), dtype=np.int64)
    for source in sources:
        lines = source.loc[source["infra"].astype(int) > int(BikeInfra.NONE)]
        if lines.empty:
            continue
        matched = conflate_lines(
            segs.reset_index(drop=True),
            lines.reset_index(drop=True),
            ["infra"],
            max_m=max_m,
            max_angle_deg=max_angle_deg,
        )
        values = pd.to_numeric(matched["infra"], errors="coerce").fillna(0).to_numpy(np.int64)
        best = np.maximum(best, values)
    return pd.Series(best, index=segs.index, dtype=np.int64)


def near_lines(segs: gpd.GeoDataFrame, lines: gpd.GeoDataFrame, radius_m: float) -> pd.Series:
    """Whether each segment comes within `radius_m` of any line, at any angle."""
    flag = np.zeros(len(segs), dtype=bool)
    if not lines.empty:
        tree = shapely.STRtree(lines.geometry.to_numpy())
        seg_idx, _ = tree.query(segs.geometry.to_numpy(), predicate="dwithin", distance=radius_m)
        flag[seg_idx] = True
    return pd.Series(flag, index=segs.index)


def strava_trips(origins: pd.DataFrame, destinations: pd.DataFrame) -> pd.Series:
    """Strava ride + e-bike trips starting or ending in each hex (hexes below the privacy
    threshold are published as 0)."""
    both = pd.concat([origins[["hex_id", "Trip_count"]], destinations[["hex_id", "Trip_count"]]])
    trips = pd.to_numeric(both["Trip_count"], errors="coerce").fillna(0.0)
    return trips.groupby(both["hex_id"]).sum().astype(float)


def hex_trips(lat: np.ndarray, lon: np.ndarray, trips: pd.Series) -> np.ndarray:
    """Trips in the res-8 hex containing each point; 0 outside published hexes."""
    cells = [
        h3.latlng_to_cell(float(a), float(o), STRAVA_H3_RES) for a, o in zip(lat, lon, strict=True)
    ]
    return trips.reindex(cells).fillna(0.0).to_numpy(float)


def ride_extra(features: pd.DataFrame) -> pd.DataFrame:
    """Ride-only design columns from `bike_infra`, `beltline_adjacent`, and `bike_trips`."""
    infra = features["bike_infra"].astype(int)
    trips = features["bike_trips"].astype(float).fillna(0.0).clip(lower=0.0)
    return pd.DataFrame(
        {
            "bike_protected": (infra == BikeInfra.PROTECTED).astype(float),
            "bike_painted": (infra == BikeInfra.PAINTED).astype(float),
            "bike_shared": (infra == BikeInfra.SHARED).astype(float),
            "beltline_adjacent": features["beltline_adjacent"].astype(float),
            "log_bike_activity": np.log1p(trips),
        },
        index=features.index,
    )
