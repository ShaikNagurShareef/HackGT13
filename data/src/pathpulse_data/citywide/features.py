"""City Pulse per-hex features and yearly pedestrian-crash labels (traffic only, NFR-14)."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pathpulse_data.citywide.hexgrid import aggregate, cells_for, parent_blocks, polygon_cells
from pathpulse_data.config import INTERIM_DIR
from pathpulse_data.network.layers import UTM, load_lines, load_points, load_streetlight

GROUPS = ("arterial", "collector", "local")


@dataclass(frozen=True)
class HexData:
    cells: pd.Index
    features: pd.DataFrame  # static per-hex features
    crashes: pd.DataFrame  # cell, year, is_ped, weight (citywide, year-only stream)
    group_share: pd.DataFrame  # road length share per road group (for temporal mixing)
    blocks: pd.Series
    centroids: pd.DataFrame  # lat, lon per cell


def _line_midpoints(lines: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray]:
    mids = gpd.GeoSeries(
        shapely.line_interpolate_point(lines.to_crs(UTM).geometry.to_numpy(), 0.5, normalized=True),
        crs=UTM,
    ).to_crs("EPSG:4326")
    return mids.y.to_numpy(), mids.x.to_numpy()


def _road_features(cells: pd.Index) -> tuple[pd.DataFrame, pd.DataFrame]:
    edges = gpd.read_parquet(INTERIM_DIR / "city_drive_edges.parquet")
    lat, lon = _line_midpoints(edges)
    ec = cells_for(lat, lon)
    km = edges["length"].to_numpy(float) / 1000.0
    lengths = pd.DataFrame(
        {
            f"km_{g}": aggregate(cells, ec, np.where(edges["road_group"] == g, km, 0.0))
            for g in GROUPS
        }
    )
    total = lengths.sum(axis=1)
    share = lengths.div(total.replace(0.0, np.nan), axis=0).fillna(0.0)
    share.columns = list(GROUPS)
    share.loc[total == 0, "local"] = 1.0
    nodes = gpd.read_parquet(INTERIM_DIR / "city_drive_nodes.parquet")
    nc = cells_for(nodes.geometry.y, nodes.geometry.x)
    feats = lengths.assign(
        intersections=aggregate(cells, nc, (nodes["street_count"].astype(float) >= 3).to_numpy()),
        signals=aggregate(
            cells, nc, (nodes["highway"].astype(str) == "traffic_signals").to_numpy()
        ),
    )
    return feats, share


def _agency_features(cells: pd.Index) -> pd.DataFrame:
    aadt = load_lines("coa_aadt_2023")
    a_lat, a_lon = _line_midpoints(aadt)
    speed = load_lines("coa_speedlimit")
    s_lat, s_lon = _line_midpoints(speed)
    bus = load_points("coa_marta_bus_stops").to_crs("EPSG:4326")
    b_cells = cells_for(bus.geometry.y, bus.geometry.x)
    sl = load_streetlight()
    sl = sl.loc[(sl["day_type"] == 0) & (sl["day_part"] == 0)].to_crs("EPSG:4326")
    return pd.DataFrame(
        {
            "log_aadt": aggregate(
                cells,
                cells_for(a_lat, a_lon),
                np.log1p(pd.to_numeric(aadt["Estimated_2023_AADT"], errors="coerce")),
                how="mean",
            ),
            "speed": aggregate(
                cells,
                cells_for(s_lat, s_lon),
                pd.to_numeric(speed["LOR_SpeedLimit"], errors="coerce").to_numpy(),
                how="mean",
            ),
            "bus_stops": aggregate(cells, b_cells),
            "log_boardings": np.log1p(
                aggregate(
                    cells, b_cells, pd.to_numeric(bus["ONS"], errors="coerce").fillna(0).to_numpy()
                )
            ),
            "log_ped_volume": aggregate(
                cells,
                cells_for(sl.geometry.y, sl.geometry.x),
                np.log1p(sl["volume"].to_numpy()),
                how="mean",
            ),
        }
    )


def build_hex_data() -> HexData:
    boundary = gpd.read_parquet(INTERIM_DIR / "city_boundary.parquet").geometry.iloc[0]
    cells = pd.Index(polygon_cells(boundary), name="cell")
    roads, share = _road_features(cells)
    feats = pd.concat([roads, _agency_features(cells)], axis=1)
    yearly = pd.read_parquet(INTERIM_DIR / "crashes_yearly.parquet")
    crash_cells = cells_for(yearly["lat"], yearly["lon"])
    crashes = pd.DataFrame(
        {
            "cell": crash_cells,
            "year": yearly["year"].astype(int).to_numpy(),
            "is_ped": yearly["is_ped"].to_numpy(),
            "weight": 1.0,
        }
    )
    crashes = crashes.loc[crashes["cell"].isin(cells)].reset_index(drop=True)
    import h3

    cent = [h3.cell_to_latlng(c) for c in cells]
    return HexData(
        cells=cells,
        features=feats,
        crashes=crashes,
        group_share=share,
        blocks=parent_blocks(cells),
        centroids=pd.DataFrame(cent, index=cells, columns=["lat", "lon"]),
    )
