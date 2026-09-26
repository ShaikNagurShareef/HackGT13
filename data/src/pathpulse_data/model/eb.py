"""Empirical Bayes (Highway Safety Manual) blend of predicted and observed crash counts.

EB = w * mu + (1 - w) * y, with w = 1 / (1 + k * mu), where mu and y are totals over the
same observation window and k is the negative-binomial overdispersion. Sites with a long,
consistent history lean on their record; sparse or noisy sites lean on the model.
"""

from __future__ import annotations

import numpy as np

MIN_K = 0.0


def estimate_overdispersion(observed: np.ndarray, predicted: np.ndarray) -> float:
    """Method-of-moments k from Var(y) = mu + k * mu^2."""
    mu = np.asarray(predicted, dtype=float)
    y = np.asarray(observed, dtype=float)
    denom = float(np.sum(mu**2))
    if denom <= 0:
        return MIN_K
    k = float(np.sum((y - mu) ** 2 - y) / denom)
    return max(k, MIN_K)


def eb_estimate(
    observed: np.ndarray, predicted: np.ndarray, k: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return (EB expected count, weight on the model) per site."""
    mu = np.asarray(predicted, dtype=float)
    w = 1.0 / (1.0 + k * mu)
    eb = w * mu + (1.0 - w) * np.asarray(observed, dtype=float)
    return eb, w
