"""Citywide 0-100 score scale and Risk Tides frame packing (PRD §7.3, NFR-02).

score = percentile of log risk density among all (segment x hour x condition x day group)
values for a model version, so "High" (75+) always means the top quartile of the city.
"""

from __future__ import annotations

import numpy as np

N_QUANTILES = 1001


def build_quantiles(log_density: np.ndarray) -> np.ndarray:
    return np.quantile(np.asarray(log_density, dtype=float), np.linspace(0.0, 1.0, N_QUANTILES))


def score_from_log_density(log_density: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    """Continuous percentile score in [0, 100] (monotone, piecewise linear)."""
    grid = np.linspace(0.0, 100.0, len(quantiles))
    return np.interp(np.asarray(log_density, dtype=float), quantiles, grid)


def pack_frames(scores: np.ndarray) -> np.ndarray:
    """(hours x segments) float scores -> flat hour-major uint8 buffer."""
    return np.clip(np.rint(scores), 0, 100).astype(np.uint8).reshape(-1)
