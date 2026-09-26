"""Assign crash points to road edges (PRD DATA-01, EC-32).

Rules, in local meter coordinates:
1. Within `node_snap_m` of a road intersection node -> split weight 1/degree across that
   node's incident road edges (intersection crashes belong to every approach).
2. Else nearest road edge within `edge_snap_m` -> weight 1.
3. Else dropped (reported by the caller).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from pathpulse_data.config import THRESHOLDS

MIN_INTERSECTION_DEGREE = 3


@dataclass(frozen=True)
class RoadIndex:
    """Spatial index over road edges (in local meters) and their intersection nodes."""

    seg_ids: np.ndarray
    geoms: np.ndarray  # shapely LineStrings
    tree: shapely.STRtree
    node_xy: np.ndarray
    node_tree: cKDTree
    node_edges: tuple[np.ndarray, ...]  # seg_ids incident to each intersection node

    @classmethod
    def from_frames(cls, edges: pd.DataFrame, nodes: pd.DataFrame) -> RoadIndex:
        geoms = np.asarray(edges["geometry"].to_list(), dtype=object)
        incident = pd.concat(
            [
                edges[["u", "seg_id"]].rename(columns={"u": "node"}),
                edges[["v", "seg_id"]].rename(columns={"v": "node"}),
            ]
        ).drop_duplicates()
        by_node = incident.groupby("node")["seg_id"].apply(lambda s: np.unique(s.to_numpy()))
        by_node = by_node[by_node.map(len) >= MIN_INTERSECTION_DEGREE]
        xy = nodes.set_index("node").loc[by_node.index, ["x", "y"]].to_numpy(float)
        return cls(
            seg_ids=edges["seg_id"].to_numpy(),
            geoms=geoms,
            tree=shapely.STRtree(geoms),
            node_xy=xy,
            node_tree=cKDTree(xy) if len(xy) else cKDTree(np.zeros((1, 2)) + 1e12),
            node_edges=tuple(by_node.to_list()),
        )


def _snap_to_nodes(index: RoadIndex, pts: np.ndarray) -> tuple[list[dict[str, float]], np.ndarray]:
    dist, nearest = index.node_tree.query(pts, distance_upper_bound=THRESHOLDS.node_snap_m)
    hit = np.isfinite(dist) & (nearest < len(index.node_edges))
    rows = [
        {
            "point_idx": int(i),
            "seg_id": int(seg),
            "weight": 1.0 / len(index.node_edges[n]),
            "dist_m": float(dist[i]),
            "snap": "node",
        }
        for i in np.flatnonzero(hit)
        for n in [int(nearest[i])]
        for seg in index.node_edges[n]
    ]
    return rows, hit


def _snap_to_edges(index: RoadIndex, pts: np.ndarray, todo: np.ndarray) -> list[dict[str, float]]:
    if not todo.any():
        return []
    points = shapely.points(pts[todo])
    pairs, dists = index.tree.query_nearest(
        points, max_distance=THRESHOLDS.edge_snap_m, return_distance=True, all_matches=False
    )
    original = np.flatnonzero(todo)
    return [
        {
            "point_idx": int(original[p]),
            "seg_id": int(index.seg_ids[g]),
            "weight": 1.0,
            "dist_m": float(d),
            "snap": "edge",
        }
        for p, g, d in zip(pairs[0], pairs[1], dists, strict=True)
    ]


def snap_points(index: RoadIndex, pts: np.ndarray) -> pd.DataFrame:
    """Return one row per (point, edge) assignment; unsnapped points are absent."""
    node_rows, hit = _snap_to_nodes(index, pts)
    edge_rows = _snap_to_edges(index, pts, ~hit)
    cols = ["point_idx", "seg_id", "weight", "dist_m", "snap"]
    return pd.DataFrame(node_rows + edge_rows, columns=cols)
