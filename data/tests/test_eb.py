"""Empirical Bayes blending of model prediction with observed history (HSM method)."""

from __future__ import annotations

import numpy as np
import pytest
from pathpulse_data.model.eb import eb_estimate, estimate_overdispersion


@pytest.mark.unit
def test_overdispersion_near_zero_for_poisson_data() -> None:
    rng = np.random.default_rng(0)
    mu = rng.uniform(0.5, 3.0, 20000)
    y = rng.poisson(mu).astype(float)

    assert estimate_overdispersion(y, mu) == pytest.approx(0.0, abs=0.02)


@pytest.mark.unit
def test_overdispersion_recovers_negative_binomial_k() -> None:
    rng = np.random.default_rng(1)
    mu = rng.uniform(0.5, 3.0, 50000)
    k = 0.8
    lam = rng.gamma(1 / k, mu * k)
    y = rng.poisson(lam).astype(float)

    assert estimate_overdispersion(y, mu) == pytest.approx(k, rel=0.1)


@pytest.mark.unit
def test_eb_between_model_and_observed() -> None:
    mu = np.array([1.0, 1.0])
    y = np.array([0.0, 5.0])

    eb, w = eb_estimate(y, mu, k=0.5)

    assert np.all((w > 0) & (w < 1))
    assert eb[0] == pytest.approx(w[0] * 1.0)
    assert 1.0 < eb[1] < 5.0


@pytest.mark.unit
def test_eb_trusts_model_when_no_overdispersion() -> None:
    eb, w = eb_estimate(np.array([7.0]), np.array([2.0]), k=0.0)

    assert w[0] == pytest.approx(1.0)
    assert eb[0] == pytest.approx(2.0)


@pytest.mark.unit
def test_eb_never_zero_when_model_positive() -> None:
    eb, _ = eb_estimate(np.array([0.0]), np.array([0.2]), k=2.0)

    assert eb[0] > 0  # PRD EC-30: zero history never means zero risk
