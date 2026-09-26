"""Street-level coverage area: the City of Atlanta boundary (PRD NFR-16: one config polygon)."""

from __future__ import annotations

from functools import cache

import geopandas as gpd
import numpy as np
import osmnx as ox
import shapely
from shapely.geometry.base import BaseGeometry

from pathpulse_data.config import CITY_NAME, INTERIM_DIR

UTM = "EPSG:32616"
EDGE_BUFFER_M = 200.0  # include streets straddling the city line
SIMPLIFY_DEG = 0.0005  # ~50 m: small enough to ship to the browser


@cache
def city_polygon() -> BaseGeometry:
    path = INTERIM_DIR / "city_boundary.parquet"
    boundary = gpd.read_parquet(path) if path.exists() else ox.geocoder.geocode_to_gdf(CITY_NAME)
    return boundary.to_crs("EPSG:4326").geometry.union_all()


@cache
def buffered_polygon(buffer_m: float = EDGE_BUFFER_M) -> BaseGeometry:
    utm = gpd.GeoSeries([city_polygon()], crs="EPSG:4326").to_crs(UTM).buffer(buffer_m)
    return utm.to_crs("EPSG:4326").iloc[0]


def contains(lon: np.ndarray, lat: np.ndarray, buffered: bool = True) -> np.ndarray:
    poly = buffered_polygon() if buffered else city_polygon()
    shapely.prepare(poly)
    return shapely.contains_xy(poly, np.asarray(lon, float), np.asarray(lat, float))


def outline_geojson() -> dict[str, object]:
    """Simplified boundary for the map outline and client-side coverage hints."""
    simple = city_polygon().simplify(SIMPLIFY_DEG, preserve_topology=True)
    return {
        "type": "Feature",
        "properties": {"name": CITY_NAME},
        "geometry": shapely.geometry.mapping(simple),
    }
