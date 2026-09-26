"""Build the pedestrian network from OpenStreetMap and classify its edges.

Unit of analysis for risk is the *road* edge; footways and crossings inherit risk
from nearby roads (see network/inherit.py).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import box

from pathpulse_data.config import CITY_NAME, CORE_BBOX, INTERIM_DIR

log = logging.getLogger(__name__)

ROAD_HIGHWAYS = frozenset(
    {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "unclassified",
        "residential",
        "living_street",
        "service",
        "road",
    }
)
ARTERIALS = frozenset({"motorway", "trunk", "primary", "secondary"})
COLLECTORS = frozenset({"tertiary", "unclassified"})
MIN_COMPONENT_SHARE = 0.98


class EdgeKind(StrEnum):
    ROAD = "road"
    CROSSING = "crossing"
    PATH = "path"


def _as_list(value: str | list[str]) -> list[str]:
    return value if isinstance(value, list) else [value]


def _base(highway: str) -> str:
    return highway.removesuffix("_link")


def classify_highway(highway: str | list[str], footway: str | None = None) -> EdgeKind:
    if footway == "crossing":
        return EdgeKind.CROSSING
    if any(_base(h) in ROAD_HIGHWAYS for h in _as_list(highway)):
        return EdgeKind.ROAD
    return EdgeKind.PATH


def road_group(highway: str | list[str]) -> str:
    bases = {_base(h) for h in _as_list(highway)}
    if bases & ARTERIALS:
        return "arterial"
    if bases & COLLECTORS:
        return "collector"
    return "local"


def largest_component_share(graph: nx.MultiDiGraph) -> float:
    if graph.number_of_nodes() == 0:
        return 0.0
    largest = max(nx.weakly_connected_components(graph), key=len)
    return len(largest) / graph.number_of_nodes()


def build_walk_graph() -> nx.MultiDiGraph:
    """Download the core-area walk network and keep its largest component."""
    west, south, east, north = CORE_BBOX
    ox.settings.useful_tags_way = [*ox.settings.useful_tags_way, "footway", "sidewalk", "lit"]
    graph = ox.graph.graph_from_polygon(box(west, south, east, north), network_type="walk")
    share = largest_component_share(graph)
    log.info("walk graph: %d nodes, largest component %.3f", graph.number_of_nodes(), share)
    if share < MIN_COMPONENT_SHARE:
        log.warning("largest component below %.2f (PRD DATA-02)", MIN_COMPONENT_SHARE)
    return ox.truncate.largest_component(graph, strongly=False)


def stringify_lists(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """OSM tags may be lists after simplification; join them so parquet can store them."""
    out = frame.copy()
    for col in out.columns:
        if col == "geometry" or out[col].dtype != object:
            continue
        if out[col].map(lambda v: isinstance(v, list)).any():
            out[col] = (
                out[col]
                .map(lambda v: ";".join(map(str, v)) if isinstance(v, list) else v)
                .astype("string")
            )
    return out


def edges_frame(graph: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    """Edge table with kind, road group, and stable integer segment ids."""
    edges = ox.convert.graph_to_gdfs(graph, nodes=False).reset_index()
    footways = edges["footway"] if "footway" in edges.columns else [None] * len(edges)
    kinds = [
        classify_highway(h, f if isinstance(f, str) else None)
        for h, f in zip(edges["highway"], footways, strict=True)
    ]
    return stringify_lists(
        edges.assign(
            kind=[k.value for k in kinds],
            road_group=[road_group(h) for h in edges["highway"]],
            seg_id=range(len(edges)),
        )
    )


ROAD_FILTER = (
    '["highway"~"^(trunk|primary|secondary|tertiary|unclassified|residential|living_street|'
    'road|service|trunk_link|primary_link|secondary_link|tertiary_link)$"]'
    '["area"!~"yes"]["access"!~"private"]'
    '["service"!~"parking_aisle|driveway|drive-through|emergency_access"]'
)


def build_core_road_graph() -> nx.MultiDiGraph:
    """Road centerlines in the core area: the unit of analysis for risk.

    OSMnx's walk network omits roads whose sidewalks are mapped separately (most of Midtown),
    so crashes -- which are geocoded to centerlines -- must snap to this graph instead.
    Interstates are excluded: pedestrians are not on them.
    """
    west, south, east, north = CORE_BBOX
    ox.settings.useful_tags_way = [*ox.settings.useful_tags_way, "lit", "sidewalk"]
    graph = ox.graph.graph_from_polygon(
        box(west, south, east, north), custom_filter=ROAD_FILTER, retain_all=True
    )
    return ox.convert.to_undirected(graph)


def road_segments_frame(graph: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    edges = ox.convert.graph_to_gdfs(graph, nodes=False).reset_index()
    return stringify_lists(
        edges.assign(
            kind=EdgeKind.ROAD.value,
            road_group=[road_group(h) for h in edges["highway"]],
            seg_id=range(len(edges)),
        )
    )


def build_city_drive_graph() -> nx.MultiDiGraph:
    """Citywide drive network used only for City Pulse hex features."""
    return ox.graph.graph_from_place(CITY_NAME, network_type="drive")


def _load_or_build(name: str, builder: Callable[[], nx.MultiDiGraph]) -> nx.MultiDiGraph:
    path = INTERIM_DIR / f"{name}.graphml"
    if path.exists():
        return ox.io.load_graphml(path)
    graph = builder()
    ox.io.save_graphml(graph, path)
    return graph


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    walk = _load_or_build("walk", build_walk_graph)
    nodes = ox.convert.graph_to_gdfs(walk, edges=False).reset_index()
    stringify_lists(nodes).to_parquet(INTERIM_DIR / "walk_nodes.parquet")
    # Walk edges are undirected for inheritance; the router rebuilds both directions.
    walk_edges = edges_frame(ox.convert.to_undirected(walk))
    walk_edges.to_parquet(INTERIM_DIR / "walk_edges.parquet")
    roads = _load_or_build("core_roads", build_core_road_graph)
    road_nodes = ox.convert.graph_to_gdfs(roads, edges=False).reset_index()
    stringify_lists(road_nodes).to_parquet(INTERIM_DIR / "road_nodes.parquet")
    road_segments = road_segments_frame(roads)
    road_segments.to_parquet(INTERIM_DIR / "road_segments.parquet")
    log.info("core road segments=%d nodes=%d", len(road_segments), len(road_nodes))
    city = _load_or_build("city_drive", build_city_drive_graph)
    city_edges = ox.convert.graph_to_gdfs(city, nodes=False).reset_index()
    city_edges = city_edges.assign(road_group=[road_group(h) for h in city_edges["highway"]])
    stringify_lists(city_edges).to_parquet(INTERIM_DIR / "city_drive_edges.parquet")
    city_nodes = ox.convert.graph_to_gdfs(city, edges=False).reset_index()
    stringify_lists(city_nodes).to_parquet(INTERIM_DIR / "city_drive_nodes.parquet")
    boundary = ox.geocoder.geocode_to_gdf(CITY_NAME)
    stringify_lists(boundary).to_parquet(INTERIM_DIR / "city_boundary.parquet")
    log.info(
        "walk nodes=%d edges=%d (road=%d) | city drive edges=%d",
        len(nodes),
        len(walk_edges),
        int((walk_edges["kind"] == "road").sum()),
        len(city_edges),
    )


if __name__ == "__main__":
    main()
