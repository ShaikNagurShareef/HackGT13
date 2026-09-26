"""Temporal/condition model B: how pedestrian crash rates shift by hour, day, light, and rain.

A multi-task Poisson GLM on stacked (cell x {all-mode, pedestrian}) counts with a log(hours)
exposure offset. All-mode crashes (~40x more data) teach the shared shape; pedestrian-specific
interaction terms learn where pedestrians differ (e.g. darkness). Output is a multiplier
normalized to average 1 over exposure within each road group, so A x B keeps A's annual scale.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

CELL_KEYS = ("road_group", "day_group", "hour", "light", "wet")
HOUR_BINS = ((0, 5, "0-5"), (6, 9, "6-9"), (10, 14, "10-14"), (15, 18, "15-18"), (19, 23, "19-23"))
LEVELS = {
    "road_group": ("arterial", "collector", "local"),
    "day_group": ("weekday", "friday", "saturday", "sunday"),
    "hour": tuple(str(h) for h in range(24)),
    "light": ("day", "twilight", "dark"),
    "hour_bin": tuple(b[2] for b in HOUR_BINS),
}
# Reference levels are dropped so every coefficient reads as "relative to a weekday daytime
# dry hour on a local street".
REFERENCE = {
    "road_group": "local",
    "day_group": "weekday",
    "hour": "12",
    "light": "day",
    "hour_bin": "10-14",
}


RATE_SCALE = 10_000.0
FACTOR_GROUPS = {
    "time_of_day": lambda c: "hour" in c,
    "day_of_week": lambda c: "day_group" in c,
    "light": lambda c: "light" in c,
    "rain": lambda c: c.endswith("wet"),
}


def hour_bin(hour: int) -> str:
    for lo, hi, label in HOUR_BINS:
        if lo <= hour <= hi:
            return label
    raise ValueError(f"hour out of range: {hour}")


def _one_hot(values: pd.Series, name: str, prefix: str) -> pd.DataFrame:
    cols = {
        f"{prefix}{name}={lvl}": (values.astype(str) == lvl).astype(float)
        for lvl in LEVELS[name]
        if lvl != REFERENCE[name]
    }
    return pd.DataFrame(cols, index=values.index)


def design(cells: pd.DataFrame, is_ped: pd.Series) -> pd.DataFrame:
    """Shared main effects + pedestrian-specific interactions."""
    ped = is_ped.astype(float).to_numpy()[:, None]
    bins = cells["hour"].astype(int).map(hour_bin)
    shared = pd.concat(
        [
            _one_hot(cells["road_group"], "road_group", ""),
            _one_hot(cells["day_group"], "day_group", ""),
            _one_hot(cells["hour"].astype(int).astype(str), "hour", ""),
            _one_hot(cells["light"], "light", ""),
            pd.DataFrame({"wet": cells["wet"].astype(float)}, index=cells.index),
        ],
        axis=1,
    )
    ped_terms = pd.concat(
        [
            _one_hot(cells["light"], "light", "ped:"),
            _one_hot(bins, "hour_bin", "ped:"),
            _one_hot(cells["day_group"], "day_group", "ped:"),
            _one_hot(cells["road_group"], "road_group", "ped:"),
            pd.DataFrame({"ped:wet": cells["wet"].astype(float)}, index=cells.index),
        ],
        axis=1,
    )
    ped_terms = ped_terms * ped
    return pd.concat(
        [pd.DataFrame({"ped": ped[:, 0]}, index=cells.index), shared, ped_terms], axis=1
    )


@dataclass(frozen=True)
class TemporalModel:
    coef: pd.Series
    intercept: float

    def log_rate(self, cells: pd.DataFrame, is_ped: bool = True) -> pd.Series:
        x = design(cells, pd.Series(is_ped, index=cells.index))[self.coef.index]
        return self.intercept + x @ self.coef

    def log_contributions(
        self, cells: pd.DataFrame, reference: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """Pedestrian log-multiplier split into readable factors plus an exact baseline.

        Columns time_of_day, day_of_week, light, rain, and _base sum to
        log(normalized_multiplier(cells, reference)).
        """
        x = design(cells, pd.Series(True, index=cells.index))[self.coef.index]
        raw = x * self.coef
        out = pd.DataFrame(
            {
                name: raw[[c for c in raw.columns if pred(c)]].sum(axis=1)
                for name, pred in FACTOR_GROUPS.items()
            },
            index=cells.index,
        )
        log_mult = np.log(self.normalized_multiplier(cells, reference))
        return out.assign(_base=log_mult - out.sum(axis=1))

    def normalized_multiplier(
        self, cells: pd.DataFrame, reference: pd.DataFrame | None = None
    ) -> pd.Series:
        """exp(log_rate) scaled so its exposure-weighted mean is 1 within each road group."""
        ref = reference if reference is not None else cells
        ref_rate = np.exp(self.log_rate(ref)) * 1.0
        norm = (
            pd.DataFrame({"rg": ref["road_group"], "r": ref_rate, "h": ref["hours"]})
            .assign(rh=lambda d: d["r"] * d["h"])
            .groupby("rg")
            .apply(lambda g: g["rh"].sum() / g["h"].sum(), include_groups=False)
        )
        return np.exp(self.log_rate(cells)) / cells["road_group"].map(norm).to_numpy()

    def pedestrian_effects(self) -> dict[str, float]:
        """Headline multipliers for pedestrians (shared + pedestrian-specific terms)."""
        c = self.coef
        return {
            "dark": float(np.exp(c.get("light=dark", 0.0) + c.get("ped:light=dark", 0.0))),
            "twilight": float(
                np.exp(c.get("light=twilight", 0.0) + c.get("ped:light=twilight", 0.0))
            ),
            "wet": float(np.exp(c.get("wet", 0.0) + c.get("ped:wet", 0.0))),
            "ped_x_dark": float(np.exp(c.get("ped:light=dark", 0.0))),
        }


def fit_temporal(counts: pd.DataFrame, alpha: float = 1e-3) -> TemporalModel:
    """Fit on rows with CELL_KEYS + is_ped + count + hours (rate target, hours weights)."""
    x = design(counts, counts["is_ped"])
    # Rates per RATE_SCALE hours keep the mean-deviance term large relative to the ridge
    # penalty (raw per-hour rates ~1e-3 would let alpha dominate and shrink real effects).
    rate = counts["count"] / counts["hours"] * RATE_SCALE
    model = PoissonRegressor(alpha=alpha, max_iter=20000, tol=1e-10)
    model.fit(x.to_numpy(float), rate.to_numpy(float), sample_weight=counts["hours"].to_numpy())
    intercept = float(model.intercept_) - float(np.log(RATE_SCALE))
    return TemporalModel(coef=pd.Series(model.coef_, index=x.columns), intercept=intercept)
