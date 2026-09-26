"""Score every method on a future holdout year against honest baselines (PRD G4)."""

from __future__ import annotations

import logging
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from pathpulse_data.config import INTERIM_DIR
from pathpulse_data.model.dataset import SegmentData, effective_length, window_counts
from pathpulse_data.model.evaluate import (
    bootstrap_ci,
    calibration_by_decile,
    poisson_deviance,
    roc_pr_auc,
    top_share_capture,
)
from pathpulse_data.model.spatial import SpatialFit, density
from pathpulse_data.network.conflate import conflate_lines
from pathpulse_data.network.layers import UTM, load_lines

log = logging.getLogger(__name__)
BOOT_REPS = 400
_TIER = re.compile(r"(\d)")


def hin_scores(data: SegmentData) -> pd.Series:
    """City of Atlanta 2025 High Injury Network tier as a ranking (Tier 1 highest)."""
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").set_index("seg_id").to_crs(UTM)
    hin = conflate_lines(segs.reset_index(), load_lines("coa_hin_2025"), ["HIN_Tier"])
    tiers = hin["HIN_Tier"].map(_tier_number)
    return pd.Series((4.0 - tiers).fillna(0.0).to_numpy(), index=segs.index)


def _tier_number(value: object) -> float:
    match = _TIER.search(str(value))
    return float(match.group(1)) if match else np.nan


def _tiebreak(scores: np.ndarray, seed: int) -> np.ndarray:
    """Random, tiny jitter so tied baselines are ranked fairly, not by row order."""
    rng = np.random.default_rng(seed)
    return scores + rng.uniform(0, 1e-9, len(scores))


def method_scores(fit: SpatialFit, data: SegmentData) -> dict[str, np.ndarray]:
    exp = fit.expected(data)
    lengths = effective_length(data.features).to_numpy()
    arc = data.features["arc_structural_count"].to_numpy(float)
    return {
        "PathPulse (EB ensemble)": density(exp["eb"], data),
        "Model only (SPF)": density(exp["spf"], data),
        "Past crash count only": _tiebreak(exp["history"].to_numpy() / (lengths / 100.0), 1),
        "City High Injury Network": _tiebreak(hin_scores(data).to_numpy(), 2),
        "ARC structural risk factors": _tiebreak(arc, 3),
        "Random": np.random.default_rng(4).uniform(size=len(lengths)),
    }


def benchmark(fit: SpatialFit, data: SegmentData, test_year: int) -> dict[str, object]:
    observed = window_counts(data, range(test_year, test_year + 1), ped=True).to_numpy()
    lengths = effective_length(data.features).to_numpy()
    scores = method_scores(fit, data)
    rows = []
    for name, s in scores.items():
        roc, pr = roc_pr_auc(s, observed)
        rows.append(
            {
                "method": name,
                "capture_top10": top_share_capture(s, observed, lengths, 0.1),
                "capture_top5": top_share_capture(s, observed, lengths, 0.05),
                "roc_auc": roc,
                "pr_auc": pr,
            }
        )
    table = pd.DataFrame(rows)

    exp = fit.expected(data)
    ours, base = scores["PathPulse (EB ensemble)"], scores["Past crash count only"]

    def cap(idx: np.ndarray, s: np.ndarray) -> float:
        return top_share_capture(s[idx], observed[idx], lengths[idx], 0.1)

    ci = bootstrap_ci(lambda i: cap(i, ours), len(observed), BOOT_REPS, seed=11)
    diff_ci = bootstrap_ci(lambda i: cap(i, ours) - cap(i, base), len(observed), BOOT_REPS, seed=12)
    calib = calibration_by_decile(exp["eb"].to_numpy(), observed)
    return {
        "test_year": test_year,
        "train_years": [fit.train_years.start, fit.train_years.stop - 1],
        "observed_ped_crashes": float(observed.sum()),
        "methods": table.to_dict(orient="records"),
        "capture_top10_ci95": ci,
        "capture_gain_vs_count_only_ci95": diff_ci,
        "deviance": {
            "eb": poisson_deviance(observed, exp["eb"].to_numpy()),
            "spf": poisson_deviance(observed, exp["spf"].to_numpy()),
            "count_only": poisson_deviance(
                observed, np.maximum(exp["history"].to_numpy() / len(fit.train_years), 1e-6)
            ),
        },
        "calibration": calib.to_dict(orient="records"),
        "fit": {
            "k": fit.k,
            "rounds": fit.rounds,
            "glm_alpha": fit.glm_alpha,
            "w_lgbm": fit.spf.weight_lgbm,
            "cv_deviance": fit.cv_deviance,
        },
    }
