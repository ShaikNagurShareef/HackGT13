"""Readable factor groups whose centered contributions reconstruct log density exactly."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.export.factors import (
    FEATURE_TO_FACTOR,
    SPATIAL_FACTORS,
    TEMPORAL_FACTORS,
    decompose,
)


@pytest.mark.unit
def test_every_model_feature_maps_to_a_factor() -> None:
    from pathpulse_data.model.dataset import FLAGS, GROUPS, NUMERIC_LOG1P, PASSTHROUGH

    features = (
        ["log_len", "log_rail_dist", "is_service", "log_nonped_density"]
        + [f"log_{c}" for c in NUMERIC_LOG1P]
        + PASSTHROUGH
        + FLAGS
        + [f"group_{g}" for g in GROUPS]
    )
    missing = [f for f in features if f not in FEATURE_TO_FACTOR]
    assert missing == []
    assert set(FEATURE_TO_FACTOR.values()) <= set(SPATIAL_FACTORS)


@pytest.mark.unit
def test_decompose_reconstructs_log_density() -> None:
    rng = np.random.default_rng(0)
    n = 50
    contrib = pd.DataFrame(rng.normal(0, 0.3, (n, 3)), columns=["log_aadt", "speed", "log_len"])
    spf_base = -3.0
    eb_adj = rng.normal(0, 0.2, n)
    log_len_100 = rng.normal(0, 0.5, n)
    road_base = rng.normal(0, 0.1, n)
    temporal = pd.DataFrame(rng.normal(0, 0.2, (7, 4)), columns=list(TEMPORAL_FACTORS))

    dec = decompose(contrib, spf_base, eb_adj, log_len_100, road_base, temporal)

    seg, cell = 13, 4
    expected = (
        spf_base
        + contrib.iloc[seg].sum()
        + eb_adj[seg]
        - log_len_100[seg]
        + road_base[seg]
        + temporal.iloc[cell].sum()
    )
    got = dec.base + dec.spatial.iloc[seg].sum() + dec.temporal.iloc[cell].sum()
    assert got == pytest.approx(expected, abs=1e-9)
    assert list(dec.spatial.columns) == list(SPATIAL_FACTORS)
    assert np.allclose(dec.spatial.mean().to_numpy(), 0.0)
