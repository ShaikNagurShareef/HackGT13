"""City Pulse: H3 hex grid over the City of Atlanta and per-hex aggregation helpers."""

from __future__ import annotations

from collections.abc import Iterable

import h3
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon

HEX_RES = 9  # ~0.1 km2 cells
BLOCK_RES = 6  # ~36 km2: grouped-CV folds for the citywide model


def polygon_cells(geom: Polygon | MultiPolygon, res: int = HEX_RES) -> list[str]:
    """All H3 cells whose centers fall inside the (multi)polygon (lon/lat)."""
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    cells: set[str] = set()
    for poly in polys:
        outer = [(lat, lon) for lon, lat in poly.exterior.coords]
        holes = [[(lat, lon) for lon, lat in ring.coords] for ring in poly.interiors]
        cells.update(h3.polygon_to_cells(h3.LatLngPoly(outer, *holes), res))
    return sorted(cells)


def cells_for(lat: Iterable[float], lon: Iterable[float], res: int = HEX_RES) -> list[str]:
    return [h3.latlng_to_cell(la, lo, res) for la, lo in zip(lat, lon, strict=True)]


def aggregate(
    cells: pd.Index, point_cells: list[str], values: np.ndarray | None = None, how: str = "sum"
) -> pd.Series:
    """Sum / mean / count of point values per hex, aligned to `cells` (missing -> 0 or NaN)."""
    vals = np.ones(len(point_cells)) if values is None else np.asarray(values, dtype=float)
    frame = pd.DataFrame({"cell": point_cells, "v": vals}).dropna()
    grouped = frame.groupby("cell")["v"]
    out = grouped.mean() if how == "mean" else grouped.sum()
    fill = np.nan if how == "mean" else 0.0
    return out.reindex(cells, fill_value=fill).astype(float)


def neighbor_sum(values: pd.Series, k: int = 1) -> pd.Series:
    """Sum of values over each hex's k-ring, excluding the hex itself."""
    lookup = values.to_dict()
    return pd.Series(
        [sum(lookup.get(n, 0.0) for n in h3.grid_disk(c, k) if n != c) for c in values.index],
        index=values.index,
        dtype=float,
    )


def parent_blocks(cells: pd.Index, res: int = BLOCK_RES) -> pd.Series:
    return pd.Series([h3.cell_to_parent(c, res) for c in cells], index=cells)
