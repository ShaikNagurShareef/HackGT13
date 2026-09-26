"""Evaluation metrics: length-budgeted top-decile capture, deviance, calibration, bootstrap."""

from __future__ import annotations

import numpy as np
import pytest
from pathpulse_data.model.evaluate import (
    bootstrap_ci,
    calibration_by_decile,
    poisson_deviance,
    top_share_capture,
)


@pytest.mark.unit
def test_capture_perfect_ranking_puts_all_crashes_in_top_budget() -> None:
    lengths = np.full(10, 100.0)
    observed = np.array([5, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=float)
    scores = np.array([9, 1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=float)

    assert top_share_capture(scores, observed, lengths, share=0.1) == pytest.approx(1.0)


@pytest.mark.unit
def test_capture_uses_length_budget_not_segment_count() -> None:
    # One very long segment with most crashes cannot all fit in a 10% length budget.
    lengths = np.array([900.0, 50.0, 50.0])
    observed = np.array([9.0, 1.0, 0.0])
    scores = np.array([1.0, 0.9, 0.1])  # density ranking

    capture = top_share_capture(scores, observed, lengths, share=0.1)

    # Budget 100 m: takes the 900 m segment only partially (100/900 of its crashes).
    assert capture == pytest.approx((9.0 * 100 / 900) / 10.0)


@pytest.mark.unit
def test_capture_random_scores_near_share() -> None:
    rng = np.random.default_rng(0)
    lengths = rng.uniform(20, 200, 5000)
    observed = rng.poisson(lengths / 1000)
    scores = rng.uniform(size=5000)

    assert top_share_capture(scores, observed, lengths, 0.1) == pytest.approx(0.1, abs=0.03)


@pytest.mark.unit
def test_poisson_deviance_zero_for_perfect_prediction() -> None:
    y = np.array([0.0, 1.0, 3.0])

    assert poisson_deviance(y, y) == pytest.approx(0.0)
    assert poisson_deviance(y, np.array([1.0, 1.0, 1.0])) > 0


@pytest.mark.unit
def test_calibration_by_decile_sums_match() -> None:
    rng = np.random.default_rng(1)
    pred = rng.gamma(1.0, 0.2, 2000)
    obs = rng.poisson(pred).astype(float)

    table = calibration_by_decile(pred, obs)

    assert len(table) == 10
    assert table["predicted"].sum() == pytest.approx(pred.sum())
    assert table["observed"].sum() == pytest.approx(obs.sum())


@pytest.mark.unit
def test_bootstrap_ci_brackets_point_estimate() -> None:
    rng = np.random.default_rng(2)
    x = rng.normal(5, 1, 400)

    lo, hi = bootstrap_ci(lambda idx: float(x[idx].mean()), n=len(x), reps=300, seed=3)

    assert lo < 5.0 < hi
