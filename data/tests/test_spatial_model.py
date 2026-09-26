"""End-to-end spatial model on synthetic segments with a known risk structure."""

from __future__ import annotations

import numpy as np
import pytest
from pathpulse_data.model.dataset import design_matrix, window_counts
from pathpulse_data.model.evaluate import top_share_capture
from pathpulse_data.model.spatial import density

from tests.conftest import N_SEG


@pytest.mark.integration
def test_window_counts_and_design_matrix_shapes(fitted: tuple) -> None:
    data, _, _ = fitted

    counts = window_counts(data, range(2019, 2021), ped=True)
    x = design_matrix(data, range(2019, 2021))

    assert len(counts) == N_SEG
    assert len(x) == N_SEG
    assert not x.isna().any().any()
    assert {"log_len", "log_aadt", "log_nonped_density", "group_arterial"} <= set(x.columns)


@pytest.mark.integration
def test_model_ranks_future_crashes_far_better_than_random(fitted: tuple) -> None:
    data, _, fit = fitted
    observed = window_counts(data, range(2023, 2024), ped=True).to_numpy()
    lengths = data.features["length_m"].to_numpy()

    scores = density(fit.expected(data)["eb"], data)
    capture = top_share_capture(scores, observed, lengths, 0.1)

    assert capture > 0.2  # random would be ~0.10


@pytest.mark.integration
def test_contributions_sum_to_log_prediction(fitted: tuple) -> None:
    data, _, fit = fitted
    x = design_matrix(data, fit.train_years)

    contrib, base = fit.spf.contributions(x)

    np.testing.assert_allclose(base + contrib.sum(axis=1), fit.spf.log_pred(x), atol=1e-6)


@pytest.mark.integration
def test_eb_weights_in_unit_interval_and_positive(fitted: tuple) -> None:
    data, _, fit = fitted

    exp = fit.expected(data)

    assert ((exp["eb_weight"] > 0) & (exp["eb_weight"] <= 1)).all()
    assert (exp["eb"] > 0).all()
    assert fit.k >= 0
