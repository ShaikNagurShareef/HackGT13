"""Safety performance function: Poisson GLM + LightGBM Poisson, ensembled in log space.

Both members output log expected annual pedestrian crashes per segment, and both expose
additive log-space contributions, so the ensemble's explanation stays exact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor
from sklearn.model_selection import GroupKFold

from pathpulse_data.model.evaluate import poisson_deviance

MONOTONE_UP = {
    "log_aadt",
    "lanes",
    "speed",
    "log_nonped_density",
    "log_ped_volume",
    "log_len",
    "log_nbr_ped_density",
    "log_nbr_nonped_density",
    "log_bike_activity",  # ride only: cycling activity proxy (exposure)
}
DEFAULT_LGB: dict[str, float | int | str] = {
    "objective": "poisson",
    "learning_rate": 0.03,
    "num_leaves": 7,
    "min_data_in_leaf": 60,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 5.0,
    "verbose": -1,
    "seed": 13,
}


@dataclass(frozen=True)
class GLMMember:
    model: PoissonRegressor
    mean: pd.Series
    scale: pd.Series

    def _z(self, x: pd.DataFrame) -> np.ndarray:
        return ((x - self.mean) / self.scale).to_numpy(float)

    def log_pred(self, x: pd.DataFrame) -> np.ndarray:
        return np.log(self.model.predict(self._z(x)))

    def contributions(self, x: pd.DataFrame) -> tuple[np.ndarray, float]:
        """Per-feature log contributions (n x p) and the shared base (intercept)."""
        return self._z(x) * self.model.coef_, float(self.model.intercept_)


@dataclass(frozen=True)
class LGBMember:
    booster: lgb.Booster

    def log_pred(self, x: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.booster.predict(x, raw_score=True), dtype=float)

    def contributions(self, x: pd.DataFrame) -> tuple[np.ndarray, float]:
        contrib = np.asarray(self.booster.predict(x, pred_contrib=True), dtype=float)
        return contrib[:, :-1], float(contrib[0, -1])


@dataclass(frozen=True)
class SPF:
    glm: GLMMember
    lgbm: LGBMember
    weight_lgbm: float
    columns: list[str] = field(default_factory=list)

    def log_pred(self, x: pd.DataFrame) -> np.ndarray:
        x = x[self.columns]
        w = self.weight_lgbm
        return w * self.lgbm.log_pred(x) + (1 - w) * self.glm.log_pred(x)

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return np.exp(self.log_pred(x))

    def contributions(self, x: pd.DataFrame) -> tuple[pd.DataFrame, float]:
        """Exact additive log contributions: base + row sum == log_pred."""
        x = x[self.columns]
        cg, bg = self.glm.contributions(x)
        cl, bl = self.lgbm.contributions(x)
        w = self.weight_lgbm
        contrib = pd.DataFrame(w * cl + (1 - w) * cg, index=x.index, columns=self.columns)
        return contrib, w * bl + (1 - w) * bg


def fit_glm(x: pd.DataFrame, rate: pd.Series, weight: pd.Series, alpha: float) -> GLMMember:
    mean, scale = x.mean(), x.std().replace(0.0, 1.0)
    model = PoissonRegressor(alpha=alpha, max_iter=3000)
    model.fit(((x - mean) / scale).to_numpy(float), rate.to_numpy(float), sample_weight=weight)
    return GLMMember(model=model, mean=mean, scale=scale)


def fit_lgbm(
    x: pd.DataFrame,
    rate: pd.Series,
    weight: pd.Series,
    params: dict[str, float | int | str],
    rounds: int,
) -> LGBMember:
    constraints = [1 if c in MONOTONE_UP else 0 for c in x.columns]
    full = {**DEFAULT_LGB, **params, "monotone_constraints": constraints}
    dataset = lgb.Dataset(x, label=rate, weight=weight, free_raw_data=False)
    return LGBMember(booster=lgb.train(full, dataset, num_boost_round=rounds))


def cv_rounds(
    x: pd.DataFrame,
    rate: pd.Series,
    weight: pd.Series,
    groups: pd.Series,
    params: dict[str, float | int | str],
    max_rounds: int = 1500,
) -> tuple[int, float]:
    """Spatial-block CV: best boosting rounds and the CV Poisson deviance."""
    constraints = [1 if c in MONOTONE_UP else 0 for c in x.columns]
    full = {**DEFAULT_LGB, **params, "monotone_constraints": constraints, "metric": "poisson"}
    folds = list(GroupKFold(n_splits=5).split(x, rate, groups))
    result = lgb.cv(
        full,
        lgb.Dataset(x, label=rate, weight=weight),
        num_boost_round=max_rounds,
        folds=folds,
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    scores = result["valid poisson-mean"]
    best = int(np.argmin(scores)) + 1
    return best, float(scores[best - 1])


def choose_ensemble_weight(
    glm_log: np.ndarray, lgb_log: np.ndarray, observed: np.ndarray, years: int
) -> float:
    """Grid-search the log-space mixing weight on held-out deviance."""
    grid = np.linspace(0.0, 1.0, 11)
    devs = [
        poisson_deviance(observed, years * np.exp(w * lgb_log + (1 - w) * glm_log)) for w in grid
    ]
    return float(grid[int(np.argmin(devs))])
