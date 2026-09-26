"""City Pulse feature build on tiny synthetic interim files (no network, no real snapshots)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.citywide import features
from pathpulse_data.citywide.features import GROUPS, build_hex_data
from pathpulse_data.citywide.hexgrid import polygon_cells
from pathpulse_data.network.layers import UTM
from shapely.geometry import LineString, Point, box

BOUNDARY = box(-84.395, 33.770, -84.385, 33.778)
HALF = 0.0002  # degrees: short lines stay inside the hex around their midpoint


def _centers() -> tuple[list[str], list[tuple[float, float]]]:
    cells = polygon_cells(BOUNDARY)
    return cells, [h3.cell_to_latlng(c) for c in cells]


def _line(lat: float, lon: float) -> LineString:
    return LineString([(lon - HALF, lat), (lon + HALF, lat)])


def _write_interim(root: Path) -> None:
    _, pts = _centers()
    (a_lat, a_lon), (b_lat, b_lon) = pts[0], pts[1]
    gpd.GeoDataFrame(geometry=[BOUNDARY], crs="EPSG:4326").to_parquet(
        root / "city_boundary.parquet"
    )
    gpd.GeoDataFrame(
        {"length": [300.0, 100.0, 200.0], "road_group": ["arterial", "local", "collector"]},
        geometry=[_line(a_lat, a_lon), _line(a_lat, a_lon), _line(b_lat, b_lon)],
        crs="EPSG:4326",
    ).to_parquet(root / "city_drive_edges.parquet")
    gpd.GeoDataFrame(
        {"street_count": [4, 3, 1], "highway": ["traffic_signals", "", "traffic_signals"]},
        geometry=[Point(a_lon, a_lat), Point(a_lon, a_lat), Point(b_lon, b_lat)],
        crs="EPSG:4326",
    ).to_parquet(root / "city_drive_nodes.parquet")
    pd.DataFrame(
        {
            "lat": [a_lat, a_lat, b_lat, 34.5],  # last crash is far outside the city
            "lon": [a_lon, a_lon, b_lon, -84.0],
            "year": [2021, 2022, 2023, 2023],
            "is_ped": [True, False, True, True],
        }
    ).to_parquet(root / "crashes_yearly.parquet")


def _utm_lines(lat: float, lon: float, **cols: list[object]) -> gpd.GeoDataFrame:
    n = len(next(iter(cols.values())))
    return gpd.GeoDataFrame(cols, geometry=[_line(lat, lon)] * n, crs="EPSG:4326").to_crs(UTM)


def _utm_points(lat: float, lon: float, **cols: list[object]) -> gpd.GeoDataFrame:
    n = len(next(iter(cols.values())))
    return gpd.GeoDataFrame(cols, geometry=[Point(lon, lat)] * n, crs="EPSG:4326").to_crs(UTM)


@pytest.fixture
def hex_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> features.HexData:
    _write_interim(tmp_path)
    (a_lat, a_lon) = _centers()[1][0]
    lines = {
        "coa_aadt_2023": _utm_lines(a_lat, a_lon, Estimated_2023_AADT=[999.0, 1999.0]),
        "coa_speedlimit": _utm_lines(a_lat, a_lon, LOR_SpeedLimit=["25", "bad"]),
    }
    bus = _utm_points(a_lat, a_lon, ONS=[10.0, None])
    light = _utm_points(
        a_lat, a_lon, day_type=[0, 0, 1], day_part=[0, 1, 0], volume=[np.e - 1, 50.0, 50.0]
    )
    monkeypatch.setattr(features, "INTERIM_DIR", tmp_path)
    monkeypatch.setattr(features, "load_lines", lambda key: lines[key])
    monkeypatch.setattr(features, "load_points", lambda key: bus)
    monkeypatch.setattr(features, "load_streetlight", lambda: light)
    return build_hex_data()


@pytest.mark.integration
def test_build_hex_data_grid_and_road_features(hex_data: features.HexData) -> None:
    cells, _ = _centers()
    a, b = cells[0], cells[1]
    f = hex_data.features

    assert list(hex_data.cells) == cells
    assert f.index.equals(hex_data.cells)
    assert (f.loc[a, ["km_arterial", "km_local", "km_collector"]] == [0.3, 0.1, 0.0]).all()
    assert f.loc[b, "km_collector"] == 0.2
    assert f.loc[a, "intersections"] == 2.0
    assert f.loc[a, "signals"] == 1.0
    assert f.loc[b, ["intersections", "signals"]].tolist() == [0.0, 1.0]


@pytest.mark.integration
def test_build_hex_data_road_share_defaults_to_local_without_roads(
    hex_data: features.HexData,
) -> None:
    cells, _ = _centers()
    share = hex_data.group_share

    assert list(share.columns) == list(GROUPS)
    np.testing.assert_allclose(share.sum(axis=1), 1.0)
    np.testing.assert_allclose(share.loc[cells[0]].to_numpy(), [0.75, 0.0, 0.25])
    assert share.loc[cells[1], "collector"] == 1.0
    empty = share.drop(index=cells[:2])
    assert len(empty) > 0
    assert (empty["local"] == 1.0).all()


@pytest.mark.integration
def test_build_hex_data_agency_features_and_crashes(hex_data: features.HexData) -> None:
    cells, _ = _centers()
    a = cells[0]
    f = hex_data.features

    assert f.loc[a, "log_aadt"] == pytest.approx(np.mean(np.log1p([999.0, 1999.0])))
    assert f.loc[a, "speed"] == 25.0  # non-numeric limit is coerced to NaN and skipped
    assert f.loc[a, "bus_stops"] == 2.0
    assert f.loc[a, "log_boardings"] == pytest.approx(np.log1p(10.0))
    assert f.loc[a, "log_ped_volume"] == pytest.approx(1.0)  # only weekday all-day rows
    assert np.isnan(f.loc[cells[1], "log_aadt"])
    assert len(hex_data.crashes) == 3  # the out-of-city crash is dropped
    assert set(hex_data.crashes["cell"]) == {a, cells[1]}
    assert (hex_data.crashes["weight"] == 1.0).all()


@pytest.mark.integration
def test_build_hex_data_centroids_and_blocks(hex_data: features.HexData) -> None:
    cells, pts = _centers()

    np.testing.assert_allclose(hex_data.centroids[["lat", "lon"]].to_numpy(), np.array(pts))
    assert all(h3.get_resolution(p) == 6 for p in hex_data.blocks)
    assert hex_data.blocks.index.equals(hex_data.cells)
    assert len(cells) >= 3
