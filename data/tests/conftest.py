"""Shared synthetic fixtures for model tests."""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.citywide.features import GROUPS, HexData
from pathpulse_data.citywide.hexgrid import polygon_cells
from pathpulse_data.citywide.model import HexFit, fit_hex
from pathpulse_data.model.dataset import (
    FLAGS,
    NUMERIC_LOG1P,
    PASSTHROUGH,
    SegmentData,
)
from pathpulse_data.model.spatial import SpatialFit, fit_spatial
from shapely.geometry import box

N_SEG = 600
YEARS = range(2019, 2024)


def _synthetic_data(seed: int = 0) -> tuple[SegmentData, np.ndarray]:
    rng = np.random.default_rng(seed)
    groups = rng.choice(["arterial", "collector", "local"], N_SEG, p=[0.2, 0.2, 0.6])
    feats = pd.DataFrame(index=pd.RangeIndex(N_SEG, name="seg_id"))
    feats["length_m"] = rng.uniform(40, 300, N_SEG)
    feats["road_group"] = groups
    feats["highway"] = np.where(groups == "local", "residential", "primary")
    for col in NUMERIC_LOG1P:
        feats[col] = rng.lognormal(3, 1, N_SEG)
    for col in PASSTHROUGH:
        feats[col] = rng.integers(0, 4, N_SEG).astype(float)
    for col in FLAGS:
        feats[col] = rng.random(N_SEG) < 0.3
    feats["rail_dist_m"] = rng.uniform(50, 2000, N_SEG)
    feats["aadt"] = np.where(
        groups == "arterial", 25000, np.where(groups == "collector", 8000, 800)
    )
    # True annual ped rate rises with traffic volume and length.
    true_rate = 0.02 * (feats["aadt"] / 1000) ** 0.6 * (feats["length_m"] / 100)
    rows = []
    for year in YEARS:
        ped = rng.poisson(true_rate)
        nonped = rng.poisson(true_rate * 20)
        for seg in range(N_SEG):
            rows += [{"seg_id": seg, "year": year, "is_ped": True, "weight": 1.0}] * int(ped[seg])
            rows += [{"seg_id": seg, "year": year, "is_ped": False, "weight": 1.0}] * int(
                nonped[seg]
            )
    crashes = pd.DataFrame(rows)
    blocks = pd.Series(np.arange(N_SEG) // 30, index=feats.index)
    cv_groups = pd.Series(np.arange(N_SEG) // 60, index=feats.index)
    data = SegmentData(features=feats, crashes=crashes, blocks=blocks, cv_groups=cv_groups)
    return data, true_rate.to_numpy()


@pytest.fixture(scope="module")
def fitted() -> tuple[SegmentData, np.ndarray, SpatialFit]:
    data, truth = _synthetic_data()
    return data, truth, fit_spatial(data, range(2019, 2023))


# --- City Pulse (citywide hex) synthetic fixtures ---------------------------------------

HEX_YEARS = range(2019, 2024)
HEX_BOX = (-84.44, 33.73, -84.38, 33.79)  # ~6 x 7 km of Atlanta -> a few hundred res-9 hexes
N_HEX_BLOCKS = 10


def synthetic_hex_data(seed: int = 0) -> HexData:
    """Real H3 cells over a small box, random features, crashes rising with arterial km."""
    rng = np.random.default_rng(seed)
    cells = pd.Index(polygon_cells(box(*HEX_BOX)), name="cell")
    n = len(cells)
    km = rng.gamma(2.0, 0.3, (n, len(GROUPS)))
    features = pd.DataFrame(km, index=cells, columns=[f"km_{g}" for g in GROUPS]).assign(
        intersections=rng.integers(0, 12, n).astype(float),
        signals=rng.integers(0, 3, n).astype(float),
        bus_stops=rng.integers(0, 5, n).astype(float),
        log_boardings=rng.uniform(0, 5, n),
        log_aadt=np.where(rng.random(n) < 0.2, np.nan, rng.uniform(6, 11, n)),
        speed=np.where(rng.random(n) < 0.2, np.nan, rng.choice([25.0, 35.0, 45.0], n)),
        log_ped_volume=np.where(rng.random(n) < 0.5, np.nan, rng.uniform(2, 8, n)),
    )
    share = pd.DataFrame(km / km.sum(axis=1, keepdims=True), index=cells, columns=list(GROUPS))
    true_rate = 0.05 + 0.4 * features["km_arterial"].to_numpy()
    rows = []
    for year in HEX_YEARS:
        for is_ped, scale in ((True, 1.0), (False, 8.0)):
            counts = rng.poisson(true_rate * scale)
            hit = np.repeat(cells.to_numpy(), counts)
            rows.append(pd.DataFrame({"cell": hit, "year": year, "is_ped": is_ped, "weight": 1.0}))
    crashes = pd.concat(rows, ignore_index=True)
    blocks = pd.Series(np.arange(n) * N_HEX_BLOCKS // n, index=cells).astype(str)
    cent = pd.DataFrame([h3.cell_to_latlng(c) for c in cells], index=cells, columns=["lat", "lon"])
    return HexData(
        cells=cells,
        features=features,
        crashes=crashes,
        group_share=share,
        blocks=blocks,
        centroids=cent,
    )


@pytest.fixture(scope="session")
def hex_fitted() -> tuple[HexData, HexFit]:
    data = synthetic_hex_data()
    return data, fit_hex(data, range(2019, 2023))
