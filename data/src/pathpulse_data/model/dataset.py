"""Segment-level design matrix and windowed crash counts for the spatial model.

Only information available *before* the prediction window may enter the design matrix:
non-pedestrian crash density is computed from the training years passed in.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

from pathpulse_data.config import INTERIM_DIR, THRESHOLDS

NUMERIC_LOG1P = ["aadt", "ped_volume", "bus_boardings", "nightlife_n", "food_n"]
PASSTHROUGH = [
    "lanes",
    "speed",
    "node_degree_max",
    "signals_n",
    "crossings_n",
    "bus_stops_n",
    "sidewalk_n",
    "sidewalk_cond",
    "arc_structural_count",
    "arc_lanes_risk",
    "arc_gdot_risk",
    "arc_high_bus_risk",
    "arc_bus_risk",
    "arc_urban_risk",
    "arc_high_dev_risk",
    "arc_min_art_risk",
    "arc_psl_risk",
    "arc_aadt_risk",
]
FLAGS = ["oneway", "state_owned", "school_zone", "osm_lit", "aadt_missing", "ped_volume_missing"]
GROUPS = ["arterial", "collector", "local"]
SPATIAL_BLOCK_RES = 8


@dataclass(frozen=True)
class SegmentData:
    """Static per-segment inputs shared by every training window."""

    features: pd.DataFrame  # indexed by seg_id
    crashes: pd.DataFrame  # snapped yearly-stream crash weights: seg_id, year, is_ped, weight
    blocks: pd.Series  # spatial block id per seg_id for grouped CV


def load_segment_data() -> SegmentData:
    feats = pd.read_parquet(INTERIM_DIR / "segment_features.parquet").set_index("seg_id")
    snaps = pd.read_parquet(INTERIM_DIR / "crash_segments.parquet")
    yearly = snaps.loc[snaps["stream"] == "yearly", ["seg_id", "year", "is_ped", "weight"]]
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").set_index("seg_id")
    mids = segs.geometry.interpolate(0.5, normalized=True)
    blocks = pd.Series(
        [h3.latlng_to_cell(p.y, p.x, SPATIAL_BLOCK_RES) for p in mids], index=segs.index
    )
    return SegmentData(features=feats, crashes=yearly, blocks=blocks)


def window_counts(data: SegmentData, years: range, ped: bool) -> pd.Series:
    """Weighted crash counts per segment over `years` (pedestrian or non-pedestrian)."""
    sel = data.crashes.loc[data.crashes["year"].isin(list(years)) & (data.crashes["is_ped"] == ped)]
    counts = sel.groupby("seg_id")["weight"].sum()
    return counts.reindex(data.features.index, fill_value=0.0)


def effective_length(features: pd.DataFrame) -> pd.Series:
    return features["length_m"].clip(lower=THRESHOLDS.min_segment_len_m)


def design_matrix(data: SegmentData, train_years: range) -> pd.DataFrame:
    """Model inputs for predicting any window after `train_years`."""
    f = data.features
    by_group = f.groupby("road_group")
    x = pd.DataFrame(index=f.index)
    x["log_len"] = np.log(effective_length(f))
    for col in NUMERIC_LOG1P:
        filled = f[col].fillna(by_group[col].transform("median")).fillna(0.0)
        x[f"log_{col}"] = np.log1p(filled.clip(lower=0.0))
    for col in PASSTHROUGH:
        x[col] = f[col].astype(float).fillna(by_group[col].transform("median")).fillna(0.0)
    for col in FLAGS:
        x[col] = f[col].astype(float)
    x["log_rail_dist"] = np.log1p(f["rail_dist_m"].fillna(f["rail_dist_m"].max()))
    for grp in GROUPS:
        x[f"group_{grp}"] = (f["road_group"] == grp).astype(float)
    x["is_service"] = (f["highway"] == "service").astype(float)
    nonped = window_counts(data, train_years, ped=False)
    per_100m_year = nonped / (effective_length(f) / 100.0) / len(train_years)
    x["log_nonped_density"] = np.log1p(per_100m_year)
    return x
