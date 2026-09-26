"""Map each walk edge to the road segment whose traffic risk it is exposed to."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from pathpulse_data.config import THRESHOLDS
from pathpulse_data.network.conflate import conflate_lines

NO_ROAD = -1
ROAD_MATCH_M = 15.0
CROSSING_MATCH_M = 20.0
ANY_ANGLE = 90.0


def inherit_segments(walk: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> pd.Series:
    """Road seg_id per walk edge (NO_ROAD for paths away from traffic). Meters CRS."""
    out = pd.Series(NO_ROAD, index=walk.index, dtype=np.int64)
    for kind, max_m, angle in (
        ("road", ROAD_MATCH_M, 30.0),
        ("path", THRESHOLDS.sidewalk_inherit_m, 30.0),
        ("crossing", CROSSING_MATCH_M, ANY_ANGLE),
    ):
        mask = walk["kind"] == kind
        if not mask.any():
            continue
        matched = conflate_lines(
            walk.loc[mask].reset_index(drop=True),
            roads,
            ["seg_id"],
            max_m=max_m,
            max_angle_deg=angle,
        )
        values = matched["seg_id"].fillna(NO_ROAD).astype(np.int64).to_numpy()
        out.loc[mask] = values
    return out
