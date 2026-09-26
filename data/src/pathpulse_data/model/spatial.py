"""Fit, validate, and test the spatial pedestrian-risk model (SPF ensemble + EB)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from pathpulse_data.model.dataset import SegmentData, design_matrix, effective_length, window_counts
from pathpulse_data.model.eb import eb_estimate, estimate_overdispersion
from pathpulse_data.model.evaluate import poisson_deviance
from pathpulse_data.model.spf import (
    SPF,
    choose_ensemble_weight,
    cv_rounds,
    fit_glm,
    fit_lgbm,
)

log = logging.getLogger(__name__)
GLM_ALPHAS = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
K_GRID = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
N_FOLDS = 5


@dataclass(frozen=True)
class SpatialFit:
    spf: SPF
    k: float
    train_years: range
    params: dict[str, float | int | str]
    rounds: int
    glm_alpha: float
    cv_deviance: float

    def expected(self, data: SegmentData) -> pd.DataFrame:
        """Annual SPF and EB expectations per segment using the training-window history."""
        x = design_matrix(data, self.train_years)
        n = len(self.train_years)
        mu = self.spf.predict(x)
        history = window_counts(data, self.train_years, ped=True).to_numpy()
        eb_total, w = eb_estimate(history, mu * n, self.k)
        return pd.DataFrame(
            {"spf": mu, "eb": eb_total / n, "eb_weight": w, "history": history},
            index=x.index,
        )


def _oof_log_preds(
    x: pd.DataFrame,
    rate: pd.Series,
    weight: pd.Series,
    groups: pd.Series,
    params: dict[str, float | int | str],
    rounds: int,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray]:
    glm_oof, lgb_oof = np.zeros(len(x)), np.zeros(len(x))
    for tr, va in GroupKFold(n_splits=N_FOLDS).split(x, rate, groups):
        g = fit_glm(x.iloc[tr], rate.iloc[tr], weight.iloc[tr], alpha)
        m = fit_lgbm(x.iloc[tr], rate.iloc[tr], weight.iloc[tr], params, rounds)
        glm_oof[va], lgb_oof[va] = g.log_pred(x.iloc[va]), m.log_pred(x.iloc[va])
    return glm_oof, lgb_oof


def _choose_glm_alpha(
    x: pd.DataFrame, rate: pd.Series, weight: pd.Series, groups: pd.Series
) -> float:
    best_alpha, best_dev = GLM_ALPHAS[0], np.inf
    folds = list(GroupKFold(n_splits=N_FOLDS).split(x, rate, groups))
    for alpha in GLM_ALPHAS:
        dev = 0.0
        for tr, va in folds:
            g = fit_glm(x.iloc[tr], rate.iloc[tr], weight.iloc[tr], alpha)
            dev += poisson_deviance(
                (rate * weight).iloc[va].to_numpy(),
                weight.iloc[va].to_numpy() * np.exp(g.log_pred(x.iloc[va])),
            )
        if dev < best_dev:
            best_alpha, best_dev = alpha, dev
    return best_alpha


def choose_k(data: SegmentData, train_years: range, annual_mu: np.ndarray) -> float:
    """Pick EB overdispersion k by predicting the last training year from the earlier ones.

    Method-of-moments k is biased toward 0 here because intersection crashes are split into
    fractional counts; a direct temporal check avoids that assumption.
    """
    if len(train_years) < 2:
        return estimate_overdispersion(
            window_counts(data, train_years, ped=True).to_numpy(), annual_mu * len(train_years)
        )
    hist_years = range(train_years.start, train_years.stop - 1)
    history = window_counts(data, hist_years, ped=True).to_numpy()
    target = window_counts(data, range(train_years.stop - 1, train_years.stop), ped=True).to_numpy()
    n = len(hist_years)
    devs = []
    for k in K_GRID:
        eb_total, _ = eb_estimate(history, annual_mu * n, k)
        devs.append(poisson_deviance(target, eb_total / n))
    return float(K_GRID[int(np.argmin(devs))])


def fit_spatial(
    data: SegmentData,
    train_years: range,
    params: dict[str, float | int | str] | None = None,
) -> SpatialFit:
    params = params or {}
    x = design_matrix(data, train_years)
    n = len(train_years)
    total = window_counts(data, train_years, ped=True)
    rate, weight = total / n, pd.Series(float(n), index=x.index)
    groups = data.cv_groups.reindex(x.index)

    rounds, cv_dev = cv_rounds(x, rate, weight, groups, params)
    alpha = _choose_glm_alpha(x, rate, weight, groups)
    glm_oof, lgb_oof = _oof_log_preds(x, rate, weight, groups, params, rounds, alpha)
    w = choose_ensemble_weight(glm_oof, lgb_oof, total.to_numpy(), n)
    oof_annual = np.exp(w * lgb_oof + (1 - w) * glm_oof)
    k = choose_k(data, train_years, oof_annual)

    spf = SPF(
        glm=fit_glm(x, rate, weight, alpha),
        lgbm=fit_lgbm(x, rate, weight, params, rounds),
        weight_lgbm=w,
        columns=list(x.columns),
    )
    log.info(
        "spatial fit %s-%s: rounds=%d alpha=%s w_lgbm=%.1f k=%.2f cv_dev=%.4f",
        train_years.start,
        train_years.stop - 1,
        rounds,
        alpha,
        w,
        k,
        cv_dev,
    )
    return SpatialFit(spf, k, train_years, params, rounds, alpha, cv_dev)


def density(values: np.ndarray | pd.Series, data: SegmentData) -> np.ndarray:
    """Per-100 m annual density used for ranking and scoring."""
    lengths = effective_length(data.features).to_numpy()
    return np.asarray(values, dtype=float) / (lengths / 100.0)
