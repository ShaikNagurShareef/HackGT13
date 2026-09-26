"""Merge the same crash reported by several overlapping sources (PRD EC-33).

Two timed records are the same crash when they share a GDOT collision id, or when they
lie within `dedupe_m` meters and `dedupe_minutes` minutes of each other.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import DisjointSet
from scipy.spatial import cKDTree

from pathpulse_data.config import THRESHOLDS

EARTH_M_PER_DEG_LAT = 111_320.0
SEVERITY_RANK = {"K": 0, "A": 1, "B": 2, "C": 3, "O": 4}


def local_xy(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Equirectangular meters around the data centroid; accurate to <0.1% over a city."""
    lat0 = float(np.nanmean(lat))
    x = (lon - np.nanmean(lon)) * EARTH_M_PER_DEG_LAT * np.cos(np.radians(lat0))
    y = (lat - lat0) * EARTH_M_PER_DEG_LAT
    return np.column_stack([x, y])


def _link_near_pairs(df: pd.DataFrame, ds: DisjointSet[int]) -> None:
    xy = local_xy(df["lat"].to_numpy(float), df["lon"].to_numpy(float))
    # Resolution-independent (pandas may store ns or us): minutes since the first crash.
    minutes = ((df["ts"] - df["ts"].min()) / pd.Timedelta(minutes=1)).to_numpy(float)
    tree = cKDTree(xy)
    for i, j in tree.query_pairs(r=THRESHOLDS.dedupe_m):
        if abs(minutes[i] - minutes[j]) <= THRESHOLDS.dedupe_minutes:
            ds.merge(i, j)


def _link_collision_ids(df: pd.DataFrame, ds: DisjointSet[int]) -> None:
    ids = df["collision_id"].dropna()
    for _, idx in ids.groupby(ids).groups.items():
        first, *rest = list(idx)
        for other in rest:
            ds.merge(first, other)


def _most_severe(values: pd.Series) -> str | None:
    ranked = [v for v in values if v in SEVERITY_RANK]
    return min(ranked, key=SEVERITY_RANK.__getitem__) if ranked else None


def _merge_cluster(group: pd.DataFrame) -> dict[str, object]:
    first = group.iloc[0]
    return {
        **first.to_dict(),
        "is_ped": bool(group["is_ped"].any()),
        "severity": _most_severe(group["severity"]),
        "light_report": group["light_report"].dropna().iloc[0]
        if group["light_report"].notna().any()
        else None,
        "surface_report": group["surface_report"].dropna().iloc[0]
        if group["surface_report"].notna().any()
        else None,
        "n_sources": int(group["source"].nunique()),
        "sources": ";".join(sorted(group["source"].unique())),
    }


def dedupe_timed(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Cluster duplicate timed crashes and merge each cluster into one record."""
    work = df.dropna(subset=["ts", "lat", "lon"]).sort_values("ts").reset_index(drop=True)
    ds: DisjointSet[int] = DisjointSet(range(len(work)))
    _link_near_pairs(work, ds)
    _link_collision_ids(work, ds)
    roots = np.array([ds[i] for i in range(len(work))])
    clusters = pd.Series(range(len(work))).groupby(roots).groups.values()
    merged = [_merge_cluster(work.iloc[list(idx)]) for idx in clusters]
    out = pd.DataFrame(merged).sort_values("ts").reset_index(drop=True)
    report = {"timed_in": len(work), "timed_out": len(out), "merged": len(work) - len(out)}
    return out, report
