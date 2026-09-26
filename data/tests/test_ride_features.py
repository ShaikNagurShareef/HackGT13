"""Ride features per road segment: bike facility class, BeltLine adjacency, cycling activity."""

from __future__ import annotations

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.network.bike import BikeInfra
from pathpulse_data.ride.features import (
    RIDE_EXTRA_COLUMNS,
    facility_by_segment,
    hex_trips,
    near_lines,
    ride_extra,
    strava_trips,
)
from shapely.geometry import LineString

UTM = "EPSG:32616"


def _lines(coords: list[list[tuple[float, float]]], **cols: list[object]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(cols, geometry=[LineString(c) for c in coords], crs=UTM)


@pytest.fixture
def segs() -> gpd.GeoDataFrame:
    return _lines(
        [[(0, 0), (100, 0)], [(200, -50), (200, 50)], [(400, 0), (500, 0)]],
        seg_id=[0, 1, 2],
    )


@pytest.mark.unit
def test_facility_takes_the_strongest_parallel_source(segs: gpd.GeoDataFrame) -> None:
    osm = _lines(
        [[(0, 5), (100, 5)], [(150, 2), (250, 2)]],  # parallel to seg 0; crosses seg 1
        infra=[int(BikeInfra.PAINTED), int(BikeInfra.PROTECTED)],
    )
    city = _lines([[(0, -4), (100, -4)]], infra=[int(BikeInfra.PROTECTED)])

    out = facility_by_segment(segs, [osm, city])

    assert out.tolist() == [int(BikeInfra.PROTECTED), int(BikeInfra.NONE), int(BikeInfra.NONE)]


@pytest.mark.unit
def test_facility_ignores_none_class_lines_even_when_nearest(segs: gpd.GeoDataFrame) -> None:
    osm = _lines(
        [[(400, 1), (500, 1)], [(400, 8), (500, 8)]],
        infra=[int(BikeInfra.NONE), int(BikeInfra.SHARED)],
    )

    out = facility_by_segment(segs, [osm])

    assert out.iloc[2] == int(BikeInfra.SHARED)


@pytest.mark.unit
def test_facility_with_no_sources_is_none(segs: gpd.GeoDataFrame) -> None:
    empty = _lines([], infra=[])

    assert facility_by_segment(segs, [empty]).tolist() == [0, 0, 0]


@pytest.mark.unit
def test_near_lines_flags_any_angle_within_radius(segs: gpd.GeoDataFrame) -> None:
    trail = _lines([[(150, 0), (250, 0)]])  # crosses seg 1 at (200, 0)

    assert near_lines(segs, trail, radius_m=10.0).tolist() == [False, True, False]
    assert near_lines(segs, _lines([]), radius_m=10.0).tolist() == [False, False, False]


@pytest.mark.unit
def test_strava_trips_sums_origins_and_destinations_per_hex() -> None:
    origins = pd.DataFrame({"hex_id": ["a", "b", "c"], "Trip_count": [10, 0, None]})
    dests = pd.DataFrame({"hex_id": ["a", "d"], "Trip_count": [5, 7]})

    out = strava_trips(origins, dests)

    assert out.to_dict() == {"a": 15.0, "b": 0.0, "c": 0.0, "d": 7.0}


@pytest.mark.unit
def test_hex_trips_looks_up_the_res8_cell_and_defaults_to_zero() -> None:
    lat, lon = np.array([33.7756, 33.70]), np.array([-84.3963, -84.50])
    cell = h3.latlng_to_cell(33.7756, -84.3963, 8)

    out = hex_trips(lat, lon, pd.Series({cell: 40.0}))

    assert out.tolist() == [40.0, 0.0]


@pytest.mark.unit
def test_ride_extra_one_hot_facility_and_log_activity() -> None:
    feats = pd.DataFrame(
        {
            "bike_infra": [0, 1, 2, 3],
            "beltline_adjacent": [False, False, True, False],
            "bike_trips": [0.0, np.nan, 9.0, 99.0],
        },
        index=pd.RangeIndex(4, name="seg_id"),
    )

    x = ride_extra(feats)

    assert list(x.columns) == list(RIDE_EXTRA_COLUMNS)
    assert x["bike_shared"].tolist() == [0.0, 1.0, 0.0, 0.0]
    assert x["bike_painted"].tolist() == [0.0, 0.0, 1.0, 0.0]
    assert x["bike_protected"].tolist() == [0.0, 0.0, 0.0, 1.0]
    assert x["beltline_adjacent"].tolist() == [0.0, 0.0, 1.0, 0.0]
    assert x["log_bike_activity"].to_numpy() == pytest.approx(np.log1p([0, 0, 9, 99]))
    assert x.index.equals(feats.index)
