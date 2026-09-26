"""Model evaluation metrics (PRD G4, §1.5).

Headline metric: of next period's pedestrian crashes, what share fall on the top X% of street
*length* when streets are ranked by predicted risk density. Ranking by length (not segment
count) prevents a model from looking good by picking long segments.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

EPS = 1e-12


def top_share_capture(
    scores: np.ndarray, observed: np.ndarray, lengths: np.ndarray, share: float = 0.1
) -> float:
    """Share of observed crashes on the top `share` of total length, ranked by score desc.

    The segment straddling the budget contributes pro-rata by length.
    """
    total = float(observed.sum())
    if total <= 0:
        return float("nan")
    order = np.argsort(-scores, kind="stable")
    lens, obs = lengths[order], observed[order]
    budget = share * lengths.sum()
    cum_before = np.concatenate([[0.0], np.cumsum(lens)[:-1]])
    take = np.clip((budget - cum_before) / np.maximum(lens, EPS), 0.0, 1.0)
    return float((obs * take).sum() / total)


def poisson_deviance(observed: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Poisson deviance; lower is better."""
    mu = np.maximum(predicted, EPS)
    y = observed
    term = np.where(y > 0, y * np.log(np.maximum(y, EPS) / mu), 0.0)
    return float(2.0 * np.mean(term - (y - mu)))


def calibration_by_decile(predicted: np.ndarray, observed: np.ndarray) -> pd.DataFrame:
    """Predicted vs observed totals per decile of predicted value."""
    ranks = pd.Series(predicted).rank(method="first")
    deciles = pd.qcut(ranks, 10, labels=False)
    frame = pd.DataFrame({"decile": deciles, "predicted": predicted, "observed": observed})
    table = frame.groupby("decile", as_index=False)[["predicted", "observed"]].sum()
    return table.assign(ratio=table["observed"] / table["predicted"].clip(lower=EPS))


def bootstrap_ci(
    stat: Callable[[np.ndarray], float],
    n: int,
    reps: int = 500,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI of `stat(indices)` resampling n units with replacement."""
    rng = np.random.default_rng(seed)
    draws = [stat(rng.integers(0, n, n)) for _ in range(reps)]
    finite = np.asarray([d for d in draws if np.isfinite(d)])
    lo, hi = np.quantile(finite, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def roc_pr_auc(scores: np.ndarray, observed: np.ndarray) -> tuple[float, float]:
    """ROC-AUC and PR-AUC for 'segment has >= 1 crash in the holdout'."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    label = (observed > 0).astype(int)
    if label.min() == label.max():
        return float("nan"), float("nan")
    return float(roc_auc_score(label, scores)), float(average_precision_score(label, scores))
