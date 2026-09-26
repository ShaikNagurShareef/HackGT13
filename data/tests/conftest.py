"""Shared synthetic fixtures for model tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.model.dataset import (
    FLAGS,
    NUMERIC_LOG1P,
    PASSTHROUGH,
    SegmentData,
)
from pathpulse_data.model.spatial import SpatialFit, fit_spatial

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
