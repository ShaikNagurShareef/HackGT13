"""Ride evaluation helpers: reuse baselines with block-bootstrap gains, targets, temporal choice."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.model.temporal_data import cell_table, fit_final
from pathpulse_data.ride.evaluate import (
    COUNT_ONLY,
    OURS,
    RANDOM,
    choose_temporal,
    compare_method,
    reuse_deviance,
    targets,
)

from tests.test_benchmark_temporal import _crashes, _hours


@pytest.mark.unit
def test_compare_method_reports_capture_and_a_positive_gain_over_noise() -> None:
    rng = np.random.default_rng(0)
    n = 400
    truth = rng.gamma(0.5, 1.0, n)
    observed = rng.poisson(truth).astype(float)
    lengths = np.full(n, 100.0)
    blocks = pd.Series(np.arange(n) // 10)

    row = compare_method("noise", truth, rng.uniform(size=n), observed, lengths, blocks, reps=60)

    assert row["method"] == "noise"
    assert 0.0 <= row["capture_top10"] <= 1.0
    assert row["capture_top5"] <= row["capture_top10"]
    lo, hi = row["gain_ci95"]
    assert 0.0 < lo <= hi


def _bench(ci_lo: float, count_only: float, random: float) -> dict[str, object]:
    return {
        "capture_top10_ci95": [ci_lo, 0.9],
        "methods": [
            {"method": OURS, "capture_top10": 0.6},
            {"method": COUNT_ONLY, "capture_top10": count_only},
            {"method": RANDOM, "capture_top10": random},
        ],
    }


@pytest.mark.unit
def test_targets_compare_ci_lower_bound_with_baselines() -> None:
    assert targets(_bench(0.5, 0.4, 0.1)) == {
        "ci_lower_above_count_only": True,
        "ci_lower_above_2x_random": True,
    }
    assert targets(_bench(0.35, 0.4, 0.2)) == {
        "ci_lower_above_count_only": False,
        "ci_lower_above_2x_random": False,
    }


@pytest.mark.unit
def test_choose_temporal_takes_lowest_deviance_and_prefers_reuse_on_ties() -> None:
    assert (
        choose_temporal(
            {"cyclist-specific": 0.9, "walk structure reused": 1.0, "all-mode shape": 1.1}
        )
        == "cyclist-specific"
    )
    assert (
        choose_temporal(
            {"cyclist-specific": 1.0, "walk structure reused": 1.0, "all-mode shape": 1.2}
        )
        == "walk structure reused"
    )


@pytest.mark.integration
def test_reuse_deviance_scores_both_task_shapes_on_held_out_target_crashes() -> None:
    hours = _hours((2019, 2020, 2021))
    crashes = _crashes(hours, seed=3)
    model = fit_final(crashes, hours, range(2019, 2021))

    target_shape = reuse_deviance(model, crashes, hours, range(2021, 2022))
    all_mode = reuse_deviance(model, crashes, hours, range(2021, 2022), target_task=False)

    assert np.isfinite(target_shape) and target_shape > 0.0
    assert np.isfinite(all_mode) and all_mode > 0.0
    assert target_shape != pytest.approx(all_mode, rel=1e-12)
    assert cell_table(crashes, hours, range(2021, 2022))["count"].sum() > 0


@pytest.mark.integration
def test_benchmark_can_score_a_model_against_a_different_crash_flag(
    fitted: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from pathpulse_data.model import benchmark as bench

    data, _, fit = fitted
    rng = np.random.default_rng(5)
    crashes = data.crashes.assign(
        is_bike=(~data.crashes["is_ped"]) & (rng.random(len(data.crashes)) < 0.05)
    )
    data = replace(data, crashes=crashes)
    monkeypatch.setattr(bench, "hin_scores", lambda d: pd.Series(0.0, index=d.features.index))
    monkeypatch.setattr(bench, "BOOT_REPS", 20)
    in_2023 = crashes["year"] == 2023

    default = bench.benchmark(fit, data, 2023)
    as_bike = bench.benchmark(fit, data, 2023, label_col="is_bike")

    assert default["observed_ped_crashes"] == pytest.approx(crashes.loc[in_2023, "is_ped"].sum())
    assert as_bike["observed_ped_crashes"] == pytest.approx(crashes.loc[in_2023, "is_bike"].sum())
    count_only = {m["method"]: m for m in as_bike["methods"]}[COUNT_ONLY]
    assert 0.0 <= count_only["capture_top10"] <= 1.0


@pytest.mark.unit
def test_pooled_target_marks_pedestrian_or_cyclist_crashes() -> None:
    from pathpulse_data.model.dataset import SegmentData
    from pathpulse_data.ride.evaluate import POOLED, with_pooled_target

    crashes = pd.DataFrame(
        {"is_ped": [True, False, False], "is_bike": [False, True, False], "weight": 1.0}
    )
    idx = pd.RangeIndex(1)
    data = SegmentData(
        features=pd.DataFrame(index=idx),
        crashes=crashes,
        blocks=pd.Series(["a"], index=idx),
        cv_groups=pd.Series(["a"], index=idx),
        target_col="is_bike",
    )

    pooled = with_pooled_target(data)

    assert pooled.target_col == POOLED
    assert pooled.crashes[POOLED].tolist() == [True, True, False]
    assert POOLED not in data.crashes.columns


@pytest.mark.unit
def test_choose_training_label_by_validation_capture() -> None:
    from pathpulse_data.ride.evaluate import choose_training

    assert choose_training({"cyclist-only": 0.60, "pedestrian+cyclist": 0.69}) == (
        "pedestrian+cyclist"
    )
    assert choose_training({"cyclist-only": 0.60, "pedestrian+cyclist": 0.60}) == "cyclist-only"
