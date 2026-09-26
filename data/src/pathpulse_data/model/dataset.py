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
from scipy.spatial import cKDTree

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
BOOTSTRAP_BLOCK_RES = 8  # ~0.7 km2: resampling unit for confidence intervals
CV_BLOCK_RES = 7  # ~5 km2: coarse enough that split intersection crashes stay in one fold
NEIGHBOR_RADIUS_M = 200.0


@dataclass(frozen=True)
class SegmentData:
    """Static per-segment inputs shared by every training window."""

    features: pd.DataFrame  # indexed by seg_id
    crashes: pd.DataFrame  # snapped yearly-stream crash weights: seg_id, year, is_ped, weight
    blocks: pd.Series  # H3 res-8 block per seg_id: bootstrap resampling unit
    cv_groups: pd.Series  # H3 res-7 block per seg_id: grouped CV folds
    xy: np.ndarray | None = None  # segment midpoints in meters (UTM), for neighborhood history
    # Crash flag the model predicts. Walk: "is_ped". Ride: "is_bike" -- the design-matrix
    # names ("ped" / "nonped") then read as "target mode" / "every other crash".
    target_col: str = "is_ped"
    extra: pd.DataFrame | None = None  # mode-specific columns appended to the design matrix


def load_segment_data() -> SegmentData:
    feats = pd.read_parquet(INTERIM_DIR / "segment_features.parquet").set_index("seg_id")
    snaps = pd.read_parquet(INTERIM_DIR / "crash_segments.parquet")
    keep = ["seg_id", "year", "is_ped", "weight"] + (["is_bike"] if "is_bike" in snaps else [])
    yearly = snaps.loc[snaps["stream"] == "yearly", keep]
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").set_index("seg_id")
    mids = segs.geometry.interpolate(0.5, normalized=True)
    mids_m = mids.to_crs("EPSG:32616")

    def cells(res: int) -> pd.Series:
        return pd.Series([h3.latlng_to_cell(p.y, p.x, res) for p in mids], index=segs.index)

    return SegmentData(
        features=feats,
        crashes=yearly,
        blocks=cells(BOOTSTRAP_BLOCK_RES),
        cv_groups=cells(CV_BLOCK_RES),
        xy=np.column_stack([mids_m.x.to_numpy(), mids_m.y.to_numpy()]),
    )


def window_counts(data: SegmentData, years: range, ped: bool) -> pd.Series:
    """Weighted crash counts per segment over `years`: target-mode crashes (`ped=True`) or all
    other crashes (`ped=False`). The target is `data.target_col` (pedestrian for walk)."""
    target = data.crashes[data.target_col]
    sel = data.crashes.loc[data.crashes["year"].isin(list(years)) & (target == ped)]
    counts = sel.groupby("seg_id")["weight"].sum()
    return counts.reindex(data.features.index, fill_value=0.0)


def effective_length(features: pd.DataFrame) -> pd.Series:
    return features["length_m"].clip(lower=THRESHOLDS.min_segment_len_m)


def neighbor_density(data: SegmentData, counts: pd.Series, years: int) -> pd.Series:
    """Crashes per year on *other* segments within NEIGHBOR_RADIUS_M, per 100 m of their length.

    Pedestrian crashes cluster along corridors, so the surrounding record carries signal the
    segment's own sparse history cannot. Uses only the counts passed in (training window).
    """
    if data.xy is None:
        return pd.Series(0.0, index=counts.index)
    tree = cKDTree(data.xy)
    lengths = effective_length(data.features).to_numpy() / 100.0
    values, out = counts.to_numpy(), np.zeros(len(counts))
    for i, nbrs in enumerate(tree.query_ball_point(data.xy, NEIGHBOR_RADIUS_M)):
        others = [j for j in nbrs if j != i]
        if others:
            out[i] = values[others].sum() / lengths[others].sum() / years
    return pd.Series(out, index=counts.index)


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
    n_years = len(train_years)
    ped = window_counts(data, train_years, ped=True)
    x["log_nbr_ped_density"] = np.log1p(100.0 * neighbor_density(data, ped, n_years))
    x["log_nbr_nonped_density"] = np.log1p(neighbor_density(data, nonped, n_years))
    if data.extra is not None:
        x = x.join(data.extra.reindex(x.index).astype(float).fillna(0.0))
    return x
