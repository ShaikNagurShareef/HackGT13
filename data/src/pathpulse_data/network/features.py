"""Structural and exposure features per road segment (no demographic features, NFR-14).

Outputs data/interim/segment_features.parquet and segment_ped_volume.parquet.
"""

from __future__ import annotations

import logging
import re

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from pathpulse_data.config import INTERIM_DIR
from pathpulse_data.network.conflate import conflate_lines, count_points_near, mean_points_near
from pathpulse_data.network.coverage import buffered_polygon
from pathpulse_data.network.layers import UTM, load_lines, load_points, load_streetlight

log = logging.getLogger(__name__)

# Structural ARC flags only; income, race, and EJ flags are deliberately excluded.
ARC_STRUCTURAL = [
    "LANES_RISK",
    "GDOT_RISK",
    "HIGH_BUS_RISK",
    "BUS_RISK",
    "URBAN_RISK",
    "HIGH_DEV_RISK",
    "MIN_ART_RISK",
    "PSL_RISK",
    "AADT_RISK",
]
NIGHTLIFE = {"bar", "pub", "nightclub", "biergarten"}
FOOD = {"restaurant", "fast_food", "cafe", "food_court"}
PED_VOLUME_RADIUS_M = 60.0
POI_RADIUS_M = 150.0
_NUM = re.compile(r"\d+(\.\d+)?")


def first_number(value: object) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    match = _NUM.search(str(value))
    return float(match.group()) if match else np.nan


def coalesce(*series: pd.Series) -> pd.Series:
    out = series[0].astype(float)
    for s in series[1:]:
        out = out.fillna(s.astype(float))
    return out


def _osm_features() -> gpd.GeoDataFrame:
    west, south, east, north = buffered_polygon().bounds
    pad = 0.002
    tags = {
        "amenity": sorted(NIGHTLIFE | FOOD),
        "highway": ["traffic_signals", "crossing"],
        "railway": ["station", "subway_entrance"],
    }
    feats = ox.features.features_from_bbox((west - pad, south - pad, east + pad, north + pad), tags)
    feats = feats.to_crs(UTM)
    return feats.assign(geometry=feats.geometry.centroid).reset_index()


def _tag_points(feats: gpd.GeoDataFrame, key: str, values: set[str]) -> gpd.GeoDataFrame:
    if key not in feats.columns:
        return feats.iloc[0:0]
    return feats.loc[feats[key].isin(values)]


def _nearest_distance(target: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.Series:
    if points.empty:
        return pd.Series(np.nan, index=target.index)
    mids = shapely.line_interpolate_point(target.geometry.to_numpy(), 0.5, normalized=True)
    xy = np.column_stack([shapely.get_x(mids), shapely.get_y(mids)])
    pxy = np.column_stack([points.geometry.x, points.geometry.y])
    dist, _ = cKDTree(pxy).query(xy)
    return pd.Series(dist, index=target.index)


def osm_columns(segs: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame) -> pd.DataFrame:
    degree = nodes.set_index("osmid")["street_count"].astype(float)
    highway = segs["highway"].astype(str).str.split(";").str[0]
    return pd.DataFrame(
        {
            "length_m": segs["length"].astype(float),
            "highway": highway,
            "road_group": segs["road_group"],
            "oneway": segs["oneway"].astype(str).str.lower().isin({"true", "yes", "1"}),
            "osm_lanes": segs["lanes"].map(first_number) if "lanes" in segs else np.nan,
            "osm_maxspeed": segs["maxspeed"].map(first_number) if "maxspeed" in segs else np.nan,
            "osm_lit": segs["lit"].astype(str).eq("yes") if "lit" in segs else False,
            "node_degree_max": np.maximum(
                segs["u"].map(degree).fillna(2), segs["v"].map(degree).fillna(2)
            ),
        },
        index=segs.index,
    )


def agency_columns(segs: gpd.GeoDataFrame) -> pd.DataFrame:
    aadt = conflate_lines(segs, load_lines("coa_aadt_2023"), ["Estimated_2023_AADT"])
    center = conflate_lines(
        segs, load_lines("coa_centerline"), ["SpeedLimit", "TOTAL_LANES", "OWNERSHIP"]
    )
    speed = conflate_lines(segs, load_lines("coa_speedlimit"), ["LOR_SpeedLimit"])
    arc = conflate_lines(segs, load_lines("arc_ped_risk_factors"), ARC_STRUCTURAL)
    arc = arc.fillna(0.0).astype(float)
    return pd.concat(
        [
            pd.DataFrame(
                {
                    "aadt": aadt["Estimated_2023_AADT"].astype(float),
                    "coa_speed": coalesce(speed["LOR_SpeedLimit"], center["SpeedLimit"]),
                    "coa_lanes": center["TOTAL_LANES"].astype(float),
                    "state_owned": center["OWNERSHIP"]
                    .astype(str)
                    .str.contains("State|GDOT", case=False, na=False),
                },
                index=segs.index,
            ),
            arc.rename(columns=lambda c: f"arc_{c.lower()}"),
            pd.Series(arc.sum(axis=1), index=segs.index, name="arc_structural_count"),
        ],
        axis=1,
    )


def context_columns(segs: gpd.GeoDataFrame, osm: gpd.GeoDataFrame) -> pd.DataFrame:
    bus = load_points("coa_marta_bus_stops")
    sidewalks = load_lines("coa_sidewalks")
    sidewalk_pts = sidewalks.assign(
        geometry=sidewalks.geometry.interpolate(0.5, normalized=True),
        cond=pd.to_numeric(sidewalks["ObservedConditionCode"], errors="coerce"),
    )
    schools = load_lines("coa_school_zones")
    return pd.DataFrame(
        {
            "signals_n": count_points_near(
                segs, _tag_points(osm, "highway", {"traffic_signals"}), 15
            ),
            "crossings_n": count_points_near(segs, _tag_points(osm, "highway", {"crossing"}), 10),
            "bus_stops_n": count_points_near(segs, bus, 40),
            "bus_boardings": count_points_near(segs, bus, 40, weight_col="ONS"),
            "sidewalk_n": count_points_near(segs, sidewalk_pts, 25),
            "sidewalk_cond": mean_points_near(segs, sidewalk_pts, "cond", 25),
            "school_zone": count_points_near(
                segs,
                schools.assign(geometry=schools.geometry.interpolate(0.5, normalized=True)),
                60,
            )
            > 0,
            "nightlife_n": count_points_near(
                segs, _tag_points(osm, "amenity", NIGHTLIFE), POI_RADIUS_M
            ),
            "food_n": count_points_near(segs, _tag_points(osm, "amenity", FOOD), POI_RADIUS_M),
            "rail_dist_m": _nearest_distance(
                segs, _tag_points(osm, "railway", {"station", "subway_entrance"})
            ),
        },
        index=segs.index,
    )


def ped_volume_tables(segs: gpd.GeoDataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """All-day pedestrian volume per segment, plus per (day_type, day_part) volumes."""
    sl = load_streetlight()
    all_day = sl.loc[(sl["day_type"] == 0) & (sl["day_part"] == 0)]
    total = mean_points_near(segs, all_day, "volume", PED_VOLUME_RADIUS_M)
    parts = []
    for (dt, dp), grp in sl.loc[(sl["day_type"] > 0) & (sl["day_part"] > 0)].groupby(
        ["day_type", "day_part"]
    ):
        vol = mean_points_near(segs, grp, "volume", PED_VOLUME_RADIUS_M)
        parts.append(
            pd.DataFrame(
                {"seg_id": segs["seg_id"], "day_type": dt, "day_part": dp, "volume": vol.to_numpy()}
            )
        )
    return total, pd.concat(parts, ignore_index=True)


def build_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").to_crs(UTM)
    nodes = gpd.read_parquet(INTERIM_DIR / "road_nodes.parquet")
    osm = _osm_features()
    ped_total, ped_parts = ped_volume_tables(segs)
    feats = pd.concat(
        [
            segs[["seg_id"]],
            osm_columns(segs, nodes),
            agency_columns(segs),
            context_columns(segs, osm),
        ],
        axis=1,
    )
    feats = feats.assign(
        lanes=coalesce(feats["osm_lanes"], feats["coa_lanes"]),
        speed=coalesce(feats["coa_speed"], feats["osm_maxspeed"]),
        ped_volume=ped_total,
        ped_volume_missing=ped_total.isna(),
        aadt_missing=feats["aadt"].isna(),
    )
    return feats, ped_parts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    feats, parts = build_features()
    feats.to_parquet(INTERIM_DIR / "segment_features.parquet", index=False)
    parts.to_parquet(INTERIM_DIR / "segment_ped_volume.parquet", index=False)
    coverage = feats.notna().mean().round(3).to_dict()
    log.info("features %s | non-null share: %s", feats.shape, coverage)


if __name__ == "__main__":
    main()
