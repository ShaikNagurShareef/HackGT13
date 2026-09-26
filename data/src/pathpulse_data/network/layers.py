"""Load raw snapshot layers as projected GeoDataFrames (meters)."""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString

from pathpulse_data.config import RAW_DIR

UTM = "EPSG:32616"


def _paths_to_geom(paths_json: str | None) -> MultiLineString | LineString | None:
    if not paths_json:
        return None
    parts = [LineString(p) for p in json.loads(paths_json) if len(p) >= 2]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else MultiLineString(parts)


def load_lines(key: str) -> gpd.GeoDataFrame:
    raw = pd.read_parquet(RAW_DIR / f"{key}.parquet")
    geoms = raw["paths"].map(_paths_to_geom)
    frame = gpd.GeoDataFrame(raw.drop(columns=["paths"]), geometry=geoms, crs="EPSG:4326")
    return frame.loc[frame.geometry.notna()].to_crs(UTM).reset_index(drop=True)


def load_points(key: str) -> gpd.GeoDataFrame:
    raw = pd.read_parquet(RAW_DIR / f"{key}.parquet").dropna(subset=["lon", "lat"])
    pts = gpd.points_from_xy(raw["lon"], raw["lat"])
    return gpd.GeoDataFrame(raw, geometry=pts, crs="EPSG:4326").to_crs(UTM).reset_index(drop=True)


def load_streetlight() -> gpd.GeoDataFrame:
    """All five StreetLight zones: pedestrian hex centroids with daily volume per period."""
    frames = [pd.read_parquet(p) for p in sorted(RAW_DIR.glob("streetlight_za*.parquet"))]
    raw = pd.concat(frames, ignore_index=True).dropna(subset=["lon", "lat"])
    raw = raw.assign(
        day_type=raw["Day_Type"].str.split(":").str[0].astype(int),
        day_part=raw["Day_Part"].str.split(":").str[0].astype(int),
        volume=pd.to_numeric(raw["Average_Daily_Zone_Traffic__StL"], errors="coerce"),
    )
    pts = gpd.points_from_xy(raw["lon"], raw["lat"])
    return gpd.GeoDataFrame(raw, geometry=pts, crs="EPSG:4326").to_crs(UTM)
