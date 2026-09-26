"""Street lighting signals: OSM `lit` tags and mapped lamps. Unknown stays unknown.

Absence of a mapped lamp is never read as "unlit": only an explicit `lit=no` tag is.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point

LIT, UNLIT, UNKNOWN = 1, 0, -1
_LIT_VALUES = frozenset({"yes", "24/7", "automatic", "sunset-sunrise", "dusk-dawn"})
_UNLIT_VALUES = frozenset({"no", "disused"})
MIN_KNOWN_SHARE = 0.5


def parse_lit(tag: object) -> int:
    if not isinstance(tag, str):
        return UNKNOWN
    value = tag.strip().lower()
    if value in _LIT_VALUES:
        return LIT
    if value in _UNLIT_VALUES:
        return UNLIT
    return UNKNOWN


def lamps_near(lines: Sequence[LineString], lamps: Sequence[Point], radius_m: float) -> np.ndarray:
    """True where a line passes within `radius_m` of any lamp (projected metres)."""
    near = np.zeros(len(lines), dtype=bool)
    if len(lamps) == 0 or len(lines) == 0:
        return near
    tree = shapely.STRtree(np.asarray(lamps, dtype=object))
    line_idx, _ = tree.query(
        np.asarray(lines, dtype=object), predicate="dwithin", distance=radius_m
    )
    near[np.unique(line_idx)] = True
    return near


def edge_lit(own: np.ndarray, segment: np.ndarray, lamp_near: np.ndarray) -> np.ndarray:
    """An edge's own tag wins, then its road segment's tag, then a nearby mapped lamp."""
    out = np.where(own != UNKNOWN, own, segment)
    out = np.where((out == UNKNOWN) & lamp_near, LIT, out)
    return out.astype(np.int8)


def hex_lit_share(
    edges: pd.DataFrame, cells: pd.Index, min_known_share: float = MIN_KNOWN_SHARE
) -> pd.Series:
    """Lit share of walkable length with known lighting; NaN when too little is known.

    `edges` has columns cell, length, lit (codes).
    """
    known = edges["lit"] != UNKNOWN
    total = edges.groupby("cell")["length"].sum().reindex(cells, fill_value=0.0)
    known_len = edges.loc[known].groupby("cell")["length"].sum().reindex(cells, fill_value=0.0)
    lit_len = (
        edges.loc[edges["lit"] == LIT]
        .groupby("cell")["length"]
        .sum()
        .reindex(cells, fill_value=0.0)
    )
    enough = (total > 0) & (known_len >= min_known_share * total)
    share = lit_len / known_len.where(known_len > 0)
    return share.where(enough)
