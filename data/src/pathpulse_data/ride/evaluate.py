"""Ride-model evaluation beyond the shared benchmark: reuse baselines and target checks."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from pathpulse_data.model.benchmark import BOOT_REPS, block_bootstrap
from pathpulse_data.model.evaluate import roc_pr_auc, top_share_capture
from pathpulse_data.model.temporal import TemporalModel
from pathpulse_data.model.temporal_data import _shape_deviance, cell_table

OURS = "PathPro (EB ensemble)"
COUNT_ONLY = "Past crash count only"
RANDOM = "Random"
WALK_REUSE = "Walk (pedestrian) model reused"
TEMPORAL_CHOICES = ("cyclist-specific", "walk structure reused", "all-mode shape")


def compare_method(
    name: str,
    ours: np.ndarray,
    other: np.ndarray,
    observed: np.ndarray,
    lengths: np.ndarray,
    blocks: pd.Series,
    reps: int = BOOT_REPS,
    seed: int = 21,
) -> dict[str, Any]:
    """Benchmark row for `other`, plus a spatial-block CI of our top-10% capture gain over it."""

    def cap(idx: np.ndarray, s: np.ndarray) -> float:
        return top_share_capture(s[idx], observed[idx], lengths[idx], 0.1)

    roc, pr = roc_pr_auc(other, observed)
    gain = block_bootstrap(lambda i: cap(i, ours) - cap(i, other), blocks, reps, seed=seed)
    return {
        "method": name,
        "capture_top10": top_share_capture(other, observed, lengths, 0.1),
        "capture_top5": top_share_capture(other, observed, lengths, 0.05),
        "roc_auc": roc,
        "pr_auc": pr,
        "gain_ci95": gain,
    }


def targets(bench: dict[str, Any]) -> dict[str, bool]:
    """Pre-registered targets: CI lower bound above count-only's point estimate, and the
    whole CI clearly above random (at least twice the random capture)."""
    methods = {m["method"]: m for m in bench["methods"]}
    lower = float(bench["capture_top10_ci95"][0])
    return {
        "ci_lower_above_count_only": lower > float(methods[COUNT_ONLY]["capture_top10"]),
        "ci_lower_above_2x_random": lower > 2.0 * float(methods[RANDOM]["capture_top10"]),
    }


def reuse_deviance(
    model: TemporalModel,
    crashes: pd.DataFrame,
    hours: pd.DataFrame,
    test_years: range,
    target_task: bool = True,
) -> float:
    """Held-out shape deviance of `model` on target-mode crashes in `test_years`.

    `target_task=True` uses the model's second-task ("ped:") terms -- e.g. the walk model's
    pedestrian shape applied to cyclist crashes; False uses its all-mode shape only.
    """
    test = cell_table(crashes, hours, test_years)
    target = test.loc[test["is_ped"].to_numpy()]
    pred = np.exp(model.log_rate(target, is_ped=target_task)) * target["hours"]
    return _shape_deviance(target["count"].to_numpy(), pred.to_numpy())


def choose_temporal(deviances: dict[str, float]) -> str:
    """Lowest held-out deviance wins; ties go to the simpler reused structure."""
    order = sorted(TEMPORAL_CHOICES, key=lambda c: (deviances[c], -TEMPORAL_CHOICES.index(c)))
    return order[0]
