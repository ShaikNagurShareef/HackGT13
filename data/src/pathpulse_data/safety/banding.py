"""Exposure-normalized crime bands: Empirical-Bayes (Poisson-Gamma) smoothing + posterior bands.

For each hex i: y_i reported crimes, E_i = expected crimes if every pedestrian-hour in the
city carried the same rate (E_i = Y * x_i / X for activity x_i). The relative rate
theta_i = y_i / E_i is noisy where E_i is small, so it is shrunk toward the city mean m
with a Gamma(alpha, alpha/m) prior whose variance is estimated by the method of moments
(Clayton & Kaldor 1987): theta_i* = (y_i + alpha) / (E_i + alpha / m).
Bands come from the Gamma posterior Gamma(y_i + alpha, E_i + alpha/m): "higher" when
P(theta_i > m) >= 0.9, "lower" when P(theta_i < m) >= 0.9, otherwise "typical" (never
"unsafe"). Citywide terciles were rejected: with ~80% of hexes at zero reports per day part
they forced hexes with no reports into "higher" only because little walking happens there.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import gamma

CRIME_BANDS: tuple[str, str, str] = ("lower", "typical", "higher")
FULL_SHRINK_ALPHA = 1e9  # no between-area variance beyond Poisson noise -> all at the mean
BAND_CONFIDENCE = 0.9


def _alpha(counts: np.ndarray, expected: np.ndarray, mean: float) -> float:
    raw = counts / expected
    weights = expected / expected.sum()
    between = float(np.sum(weights * (raw - mean) ** 2)) - mean / float(expected.mean())
    if between <= 0:
        return FULL_SHRINK_ALPHA
    return mean**2 / between


def _posterior(counts: np.ndarray, exposure: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Gamma posterior (shape, rate) per area and the citywide mean relative rate m."""
    y = np.asarray(counts, dtype=float)
    x = np.asarray(exposure, dtype=float)
    expected = np.maximum(y.sum() * x / x.sum(), 1e-9)
    mean = float(y.sum() / expected.sum())
    alpha = _alpha(y, expected, mean)
    return y + alpha, expected + alpha / mean, mean


def eb_relative_rate(counts: np.ndarray, exposure: np.ndarray) -> np.ndarray:
    """Posterior-mean relative rate per area (1.0 = the citywide rate per unit exposure)."""
    y = np.asarray(counts, dtype=float)
    if y.sum() <= 0:
        return np.ones_like(y)
    shape, rate, _ = _posterior(y, exposure)
    return shape / rate


def posterior_bands(
    counts: np.ndarray, exposure: np.ndarray, confidence: float = BAND_CONFIDENCE
) -> np.ndarray:
    """Band "higher" or "lower" only when the posterior is confident, else "typical"."""
    y = np.asarray(counts, dtype=float)
    if y.sum() <= 0:
        return np.full(len(y), CRIME_BANDS[1])
    shape, rate, mean = _posterior(y, exposure)
    above = gamma.sf(mean, shape, scale=1 / rate)
    below = gamma.cdf(mean, shape, scale=1 / rate)
    higher = (above >= confidence) & (y > 0)  # no reports can never read as "higher"
    return np.where(
        higher, CRIME_BANDS[2], np.where(below >= confidence, CRIME_BANDS[0], CRIME_BANDS[1])
    )
