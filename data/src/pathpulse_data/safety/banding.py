"""Exposure-normalized crime bands: Empirical-Bayes (Poisson-Gamma) smoothing + terciles.

For each hex i: y_i reported crimes, E_i = expected crimes if every pedestrian-hour in the
city carried the same rate (E_i = Y * x_i / X for activity x_i). The relative rate
theta_i = y_i / E_i is noisy where E_i is small, so it is shrunk toward the city mean m
with a Gamma(alpha, alpha/m) prior whose variance is estimated by the method of moments
(Clayton & Kaldor 1987): theta_i* = (y_i + alpha) / (E_i + alpha / m).
Bands are citywide terciles of theta_i*: "lower", "typical", "higher" (never "unsafe").
"""

from __future__ import annotations

import numpy as np

CRIME_BANDS: tuple[str, str, str] = ("lower", "typical", "higher")
FULL_SHRINK_ALPHA = 1e9  # no between-area variance beyond Poisson noise -> all at the mean
LOWER_Q, UPPER_Q = 1 / 3, 2 / 3


def _alpha(counts: np.ndarray, expected: np.ndarray, mean: float) -> float:
    raw = counts / expected
    weights = expected / expected.sum()
    between = float(np.sum(weights * (raw - mean) ** 2)) - mean / float(expected.mean())
    if between <= 0:
        return FULL_SHRINK_ALPHA
    return mean**2 / between


def eb_relative_rate(counts: np.ndarray, exposure: np.ndarray) -> np.ndarray:
    """Posterior-mean relative rate per area (1.0 = the citywide rate per unit exposure)."""
    y = np.asarray(counts, dtype=float)
    x = np.asarray(exposure, dtype=float)
    if y.sum() <= 0:
        return np.ones_like(y)
    expected = np.maximum(y.sum() * x / x.sum(), 1e-9)
    mean = float(y.sum() / expected.sum())
    alpha = _alpha(y, expected, mean)
    return (y + alpha) / (expected + alpha / mean)


def tercile_bands(values: np.ndarray) -> np.ndarray:
    """Citywide terciles; ties fall to the lower band so "higher" is never inflated."""
    v = np.asarray(values, dtype=float)
    lo, hi = np.quantile(v, [LOWER_Q, UPPER_Q])
    return np.where(v <= lo, CRIME_BANDS[0], np.where(v <= hi, CRIME_BANDS[1], CRIME_BANDS[2]))
