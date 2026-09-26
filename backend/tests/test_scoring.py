"""Score scale, bands, and telescoping factor attribution (PRD EXP-01, §7.3)."""

from __future__ import annotations

import numpy as np
import pytest
from app.domain.scoring import (
    Band,
    attribute,
    band_for,
    score_from_log_density,
)
from hypothesis import given, settings
from hypothesis import strategies as st

QUANTILES = np.linspace(-6.0, 2.0, 1001)  # log density -6 -> score 0, +2 -> 100


@pytest.mark.unit
@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0, Band.LOWER),
        (24, Band.LOWER),
        (25, Band.MODERATE),
        (49, Band.MODERATE),
        (50, Band.ELEVATED),
        (74, Band.ELEVATED),
        (75, Band.HIGH),
        (100, Band.HIGH),
    ],
)
def test_band_for(score: int, band: Band) -> None:
    assert band_for(score) is band


@pytest.mark.unit
def test_score_interpolates_and_clips() -> None:
    scores = score_from_log_density(np.array([-10.0, -2.0, 5.0]), QUANTILES)

    assert scores.tolist() == pytest.approx([0.0, 50.0, 100.0])


@pytest.mark.unit
def test_attribution_orders_by_magnitude_and_keeps_signs() -> None:
    factors = {"speed": 1.0, "rain": -0.25, "lanes": 0.5}

    result = attribute(base=-2.0, factors=factors, quantiles=QUANTILES, top_n=5)

    keys = [f.key for f in result.factors]
    assert keys == ["speed", "lanes", "rain"]
    assert result.factors[0].points > 0
    assert result.factors[2].points < 0


@pytest.mark.unit
def test_attribution_parts_sum_to_displayed_score() -> None:
    factors = {f"f{i}": v for i, v in enumerate([0.9, -0.4, 0.3, 0.2, -0.1, 0.05, 0.02])}

    result = attribute(base=-2.5, factors=factors, quantiles=QUANTILES, top_n=5)

    parts = result.baseline_points + sum(f.points for f in result.factors) + result.remainder_points
    assert parts == result.score
    assert len(result.factors) == 5


@settings(max_examples=200, deadline=None)
@given(
    base=st.floats(-8, 4),
    values=st.lists(st.floats(-2, 2, allow_nan=False), min_size=1, max_size=18),
)
def test_attribution_always_sums_exactly(base: float, values: list[float]) -> None:
    factors = {f"f{i}": v for i, v in enumerate(values)}

    result = attribute(base=base, factors=factors, quantiles=QUANTILES, top_n=5)

    parts = result.baseline_points + sum(f.points for f in result.factors) + result.remainder_points
    assert parts == result.score
    assert 0 <= result.score <= 100
