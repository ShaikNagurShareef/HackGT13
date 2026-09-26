"""Help points: GT blue-light call boxes, police, fire stations, hospitals, MARTA rail."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from pathpulse_data.citywide.hexgrid import cells_for

HELP_KINDS: tuple[str, ...] = ("blue_light", "police", "fire", "hospital", "marta")
_AMENITY_KIND = {"police": "police", "fire_station": "fire", "hospital": "hospital"}
DEFAULT_NAMES = {
    "blue_light": "Emergency call box",
    "police": "Police station",
    "fire": "Fire station",
    "hospital": "Hospital",
    "marta": "MARTA station",
}
M_PER_DEG = 111_320.0
REF_LAT = 33.7756
DEDUPE_M = 30.0
COLUMNS = ["kind", "name", "lat", "lon"]


def _clean_name(name: object, kind: str) -> str:
    text = name.strip() if isinstance(name, str) else ""
    return text or DEFAULT_NAMES[kind]


def _is_marta(row: pd.Series) -> bool:
    labels = f"{row.get('network') or ''} {row.get('operator') or ''}".upper()
    is_station = row.get("railway") == "station"
    return is_station and ("MARTA" in labels or "METROPOLITAN ATLANTA RAPID TRANSIT" in labels)


def _kind(row: pd.Series) -> str | None:
    amenity = row.get("amenity")
    if isinstance(amenity, str) and amenity in _AMENITY_KIND:
        return _AMENITY_KIND[amenity]
    if _is_marta(row):
        return "marta"
    return None


def osm_help_points(raw: pd.DataFrame) -> pd.DataFrame:
    kinds = raw.apply(_kind, axis=1)
    rows = raw.assign(kind=kinds).loc[kinds.notna()]
    names = [_clean_name(n, k) for n, k in zip(rows["name"], rows["kind"], strict=True)]
    return rows.assign(name=names)[COLUMNS].reset_index(drop=True)


def callbox_points(raw: pd.DataFrame) -> pd.DataFrame:
    """Active outdoor GT call boxes (indoor phones are not reachable from the street)."""
    keep = raw["phone_status"].eq("Active") & raw["location_code"].eq("Outside")
    rows = raw.loc[keep]
    return pd.DataFrame(
        {
            "kind": "blue_light",
            "name": [_clean_name(n, "blue_light") for n in rows["phone_name"]],
            "lat": rows["lat"].to_numpy(float),
            "lon": rows["lon"].to_numpy(float),
        }
    )[COLUMNS]


def _local_xy(lonlat: np.ndarray) -> np.ndarray:
    kx = M_PER_DEG * np.cos(np.radians(REF_LAT))
    return np.column_stack([lonlat[:, 0] * kx, lonlat[:, 1] * M_PER_DEG])


def dedupe_points(points: pd.DataFrame, radius_m: float = DEDUPE_M) -> pd.DataFrame:
    """Drop a point when an earlier point of the same kind lies within `radius_m`."""
    keep: list[int] = []
    for _, group in points.groupby("kind", sort=False):
        xy = _local_xy(group[["lon", "lat"]].to_numpy(float))
        taken = np.zeros(len(group), dtype=bool)
        tree = cKDTree(xy)
        for i in range(len(group)):
            if taken[i]:
                continue
            keep.append(int(group.index[i]))
            taken[tree.query_ball_point(xy[i], radius_m)] = True
    return points.loc[sorted(keep)].reset_index(drop=True)


def hex_help_counts(points: pd.DataFrame, cells: pd.Index) -> pd.Series:
    counts = pd.Series(cells_for(points["lat"], points["lon"])).value_counts()
    return counts.reindex(cells, fill_value=0).astype(np.int64)


def nearest_distance_m(targets_lonlat: np.ndarray, points_lonlat: np.ndarray) -> np.ndarray:
    if len(points_lonlat) == 0:
        return np.full(len(targets_lonlat), np.nan)
    dist, _ = cKDTree(_local_xy(points_lonlat)).query(_local_xy(targets_lonlat))
    return np.asarray(dist, dtype=float)
