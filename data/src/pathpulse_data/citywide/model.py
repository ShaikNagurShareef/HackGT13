"""City Pulse model: hex-level SPF ensemble + Empirical Bayes, evaluated on a future year."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pathpulse_data.citywide.features import HexData
from pathpulse_data.citywide.hexgrid import neighbor_sum
from pathpulse_data.model.eb import eb_estimate
from pathpulse_data.model.evaluate import poisson_deviance, roc_pr_auc, top_share_capture
from pathpulse_data.model.spatial import K_GRID
from pathpulse_data.model.spf import SPF, choose_ensemble_weight, cv_rounds, fit_glm, fit_lgbm

log = logging.getLogger(__name__)
GLM_ALPHA = 0.01


def hex_counts(data: HexData, years: range, ped: bool) -> pd.Series:
    sel = data.crashes.loc[data.crashes["year"].isin(list(years)) & (data.crashes["is_ped"] == ped)]
    return sel.groupby("cell")["weight"].sum().reindex(data.cells, fill_value=0.0)


def hex_design(data: HexData, train_years: range) -> pd.DataFrame:
    f = data.features
    x = pd.DataFrame(index=data.cells)
    for col in ("km_arterial", "km_collector", "km_local", "intersections", "signals", "bus_stops"):
        x[col] = f[col].astype(float)
    for col in ("log_aadt", "speed", "log_ped_volume"):
        x[col] = f[col].fillna(f[col].median())
        x[f"{col}_missing"] = f[col].isna().astype(float)
    x["log_boardings"] = f["log_boardings"]
    n = len(train_years)
    nonped = hex_counts(data, train_years, ped=False)
    ped = hex_counts(data, train_years, ped=True)
    x["log_nonped"] = np.log1p(nonped / n)
    x["log_nbr_ped"] = np.log1p(neighbor_sum(ped) / n)
    x["log_nbr_nonped"] = np.log1p(neighbor_sum(nonped) / n)
    return x


@dataclass(frozen=True)
class HexFit:
    spf: SPF
    k: float
    train_years: range

    def expected(self, data: HexData) -> pd.DataFrame:
        x = hex_design(data, self.train_years)
        n = len(self.train_years)
        mu = self.spf.predict(x)
        hist = hex_counts(data, self.train_years, ped=True).to_numpy()
        eb_total, _ = eb_estimate(hist, mu * n, self.k)
        return pd.DataFrame({"spf": mu, "eb": eb_total / n, "history": hist}, index=data.cells)


def _choose_k(data: HexData, years: range, annual_mu: np.ndarray) -> float:
    hist_years = range(years.start, years.stop - 1)
    hist = hex_counts(data, hist_years, ped=True).to_numpy()
    target = hex_counts(data, range(years.stop - 1, years.stop), ped=True).to_numpy()
    n = len(hist_years)
    devs = [poisson_deviance(target, eb_estimate(hist, annual_mu * n, k)[0] / n) for k in K_GRID]
    return float(K_GRID[int(np.argmin(devs))])


def fit_hex(data: HexData, train_years: range) -> HexFit:
    x = hex_design(data, train_years)
    n = len(train_years)
    total = hex_counts(data, train_years, ped=True)
    rate, weight = total / n, pd.Series(float(n), index=x.index)
    groups = data.blocks.reindex(x.index)
    rounds, _ = cv_rounds(x, rate, weight, groups, {})
    glm = fit_glm(x, rate, weight, GLM_ALPHA)
    lgbm = fit_lgbm(x, rate, weight, {}, rounds)
    w = choose_ensemble_weight(glm.log_pred(x), lgbm.log_pred(x), total.to_numpy(), n)
    spf = SPF(glm=glm, lgbm=lgbm, weight_lgbm=w, columns=list(x.columns))
    k = _choose_k(data, train_years, spf.predict(x))
    log.info(
        "hex fit %s-%s rounds=%d w=%.1f k=%.2f",
        train_years.start,
        train_years.stop - 1,
        rounds,
        w,
        k,
    )
    return HexFit(spf=spf, k=k, train_years=train_years)


def benchmark_hex(fit: HexFit, data: HexData, test_year: int) -> dict[str, object]:
    observed = hex_counts(data, range(test_year, test_year + 1), ped=True).to_numpy()
    exp = fit.expected(data)
    ones = np.ones(len(observed))
    rng = np.random.default_rng(7)
    methods = {
        "City Pulse (EB ensemble)": exp["eb"].to_numpy(),
        "Past crash count only": exp["history"].to_numpy() + rng.uniform(0, 1e-9, len(ones)),
        "Random": rng.uniform(size=len(ones)),
    }
    rows = []
    for name, s in methods.items():
        roc, pr = roc_pr_auc(s, observed)
        rows.append(
            {
                "method": name,
                "capture_top10": top_share_capture(s, observed, ones, 0.1),
                "roc_auc": roc,
                "pr_auc": pr,
            }
        )
    return {
        "test_year": test_year,
        "n_hexes": len(observed),
        "observed_ped_crashes": float(observed.sum()),
        "methods": rows,
    }
