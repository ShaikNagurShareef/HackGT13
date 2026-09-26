"""Ride (bike, e-bike, scooter) network and bike-infrastructure classes.

The risk unit stays the road centerline segment (crashes are geocoded to centerlines); the
OSMnx bike network is the *routing* graph, and its edges inherit risk from those segments
exactly like walk edges do. Dedicated paths away from traffic (e.g. the Atlanta BeltLine)
inherit no road and carry no traffic exposure.

Usage: uv run --package pathpulse-data python -m pathpulse_data.network.bike
"""

from __future__ import annotations

import logging
import re
from enum import IntEnum

import networkx as nx
import osmnx as ox
import pandas as pd

from pathpulse_data.config import INTERIM_DIR
from pathpulse_data.network.coverage import buffered_polygon
from pathpulse_data.network.graph import (
    MIN_COMPONENT_SHARE,
    _load_or_build,
    edges_frame,
    largest_component_share,
    stringify_lists,
)

log = logging.getLogger(__name__)

CYCLEWAY_TAGS = ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both")
BIKE_WAY_TAGS = (*CYCLEWAY_TAGS, "bicycle", "segregated", "lit")
BELTLINE = re.compile(r"belt\s?line|eastside trail|westside trail|southside trail", re.IGNORECASE)


class BikeInfra(IntEnum):
    """Bike facility on (or alongside) a street, strongest first when several apply."""

    NONE = 0
    SHARED = 1  # sharrows, bike boulevards / neighborhood greenways
    PAINTED = 2  # painted or buffered lane
    PROTECTED = 3  # physically separated lane, cycle track, or parallel shared-use path


_OSM_CYCLEWAY = {
    "track": BikeInfra.PROTECTED,
    "separate": BikeInfra.PROTECTED,  # facility mapped as its own way alongside the road
    "lane": BikeInfra.PAINTED,
    "buffered_lane": BikeInfra.PAINTED,
    "opposite_lane": BikeInfra.PAINTED,
    "opposite_track": BikeInfra.PROTECTED,
    "shared_lane": BikeInfra.SHARED,
    "share_busway": BikeInfra.SHARED,
    "opposite_share_busway": BikeInfra.SHARED,
}
_CITY_SIMPLE = {
    "protected bike lane": BikeInfra.PROTECTED,
    "shared-use path": BikeInfra.PROTECTED,
    "painted bike lane": BikeInfra.PAINTED,
    "painted bike lanes": BikeInfra.PAINTED,
    "bike-friendly street": BikeInfra.SHARED,
}


def _values(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return []
    return [v.strip().lower() for v in str(value).split(";") if v.strip()]


def osm_infra(tags: dict[str, object]) -> BikeInfra:
    """Strongest facility named by an OSM way's cycleway / highway / bicycle tags."""
    highway = _values(tags.get("highway"))
    if "cycleway" in highway:
        return BikeInfra.PROTECTED
    if "path" in highway and "designated" in _values(tags.get("bicycle")):
        return BikeInfra.PROTECTED
    found = [
        _OSM_CYCLEWAY[v]
        for key in CYCLEWAY_TAGS
        for v in _values(tags.get(key))
        if v in _OSM_CYCLEWAY
    ]
    return max(found, default=BikeInfra.NONE)


def city_infra(simple_type: object, status: object) -> BikeInfra:
    """City of Atlanta Bike_Facilities class; only facilities with Status 'Existing' count."""
    if str(status).strip().lower() != "existing":
        return BikeInfra.NONE
    return _CITY_SIMPLE.get(str(simple_type).strip().lower(), BikeInfra.NONE)


def is_beltline(name: object) -> bool:
    return any(BELTLINE.search(v) for v in _values(name))


def build_bike_graph() -> nx.MultiDiGraph:
    """Download the citywide OSMnx bike network and keep its largest component."""
    ox.settings.useful_tags_way = sorted({*ox.settings.useful_tags_way, *BIKE_WAY_TAGS})
    graph = ox.graph.graph_from_polygon(buffered_polygon(), network_type="bike")
    share = largest_component_share(graph)
    log.info("bike graph: %d nodes, largest component %.3f", graph.number_of_nodes(), share)
    if share < MIN_COMPONENT_SHARE:
        log.warning("bike graph largest component below %.2f", MIN_COMPONENT_SHARE)
    return ox.truncate.largest_component(graph, strongly=False)


def bike_edges_frame(graph: nx.MultiDiGraph) -> pd.DataFrame:
    """Undirected bike edges with kind, road group, seg ids, infra class, and BeltLine flag."""
    edges = edges_frame(ox.convert.to_undirected(graph))
    records = edges.drop(columns="geometry").to_dict("records")
    names = edges["name"] if "name" in edges.columns else pd.Series([None] * len(edges))
    out: pd.DataFrame = edges.assign(
        bike_infra=[int(osm_infra(r)) for r in records],
        beltline=[is_beltline(n) for n in names],
    )
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    graph = _load_or_build("city_bike", build_bike_graph)
    nodes = ox.convert.graph_to_gdfs(graph, edges=False).reset_index()
    stringify_lists(nodes).to_parquet(INTERIM_DIR / "bike_nodes.parquet")
    edges = bike_edges_frame(graph)
    edges.to_parquet(INTERIM_DIR / "bike_edges.parquet")
    log.info(
        "bike nodes=%d edges=%d (road=%d path=%d beltline=%d infra>0=%d)",
        len(nodes),
        len(edges),
        int((edges["kind"] == "road").sum()),
        int((edges["kind"] == "path").sum()),
        int(edges["beltline"].sum()),
        int((edges["bike_infra"] > 0).sum()),
    )


if __name__ == "__main__":
    main()
