"""Citywide percentile score scale and uint8 Risk Tides frames."""

from __future__ import annotations

import numpy as np
import pytest
from pathpulse_data.export.frames import (
    N_QUANTILES,
    build_quantiles,
    pack_frames,
    score_from_log_density,
)


@pytest.mark.unit
def test_scores_span_zero_to_hundred_and_are_monotonic() -> None:
    rng = np.random.default_rng(0)
    values = rng.normal(0, 1, 50_000)
    q = build_quantiles(values)

    scores = score_from_log_density(np.sort(values), q)

    assert len(q) == N_QUANTILES
    assert scores.min() == pytest.approx(0.0, abs=0.5)
    assert scores.max() == pytest.approx(100.0, abs=0.5)
    assert np.all(np.diff(scores) >= -1e-9)


@pytest.mark.unit
def test_score_is_percentile() -> None:
    values = np.arange(1000, dtype=float)
    q = build_quantiles(values)

    assert score_from_log_density(np.array([749.0]), q)[0] == pytest.approx(75.0, abs=0.2)


@pytest.mark.unit
def test_out_of_range_values_clip() -> None:
    q = build_quantiles(np.arange(100, dtype=float))

    assert score_from_log_density(np.array([-1e9, 1e9]), q).tolist() == [0.0, 100.0]


@pytest.mark.unit
def test_pack_frames_layout_is_hour_major_uint8() -> None:
    scores = np.array([[0.4, 99.6, 50.0], [10.0, 20.0, 30.0]])  # 2 hours x 3 segments

    packed = pack_frames(scores)

    assert packed.dtype == np.uint8
    assert packed.tolist() == [0, 100, 50, 10, 20, 30]
