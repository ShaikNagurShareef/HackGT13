"""Temporal/condition multiplier model: recovers known effects with exposure offsets."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.model.temporal import (
    CELL_KEYS,
    TemporalModel,
    fit_temporal,
    hour_bin,
)


def _synthetic(
    dark_mult: float, wet_mult: float, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    cells = []
    for rg in ("arterial", "collector", "local"):
        for dg in ("weekday", "friday", "saturday", "sunday"):
            for hour in range(24):
                for light in ("day", "twilight", "dark"):
                    for wet in (False, True):
                        cells.append((rg, dg, hour, light, wet))
    exp = pd.DataFrame(cells, columns=["road_group", "day_group", "hour", "light", "wet"])
    exp["hours"] = rng.uniform(50, 400, len(exp))
    base = {"arterial": 0.02, "collector": 0.01, "local": 0.004}
    rows = []
    for is_ped in (False, True):
        mult = np.where(exp["light"] == "dark", dark_mult if is_ped else 1.2, 1.0)
        mult = mult * np.where(exp["wet"], wet_mult, 1.0)
        mu = exp["hours"] * exp["road_group"].map(base) * (0.2 if is_ped else 1.0) * mult
        rows.append(exp.assign(is_ped=is_ped, count=rng.poisson(mu)))
    counts = pd.concat(rows, ignore_index=True)
    return counts, exp


@pytest.mark.unit
def test_hour_bin() -> None:
    assert [hour_bin(h) for h in (0, 5, 6, 9, 10, 14, 15, 18, 19, 23)] == [
        "0-5",
        "0-5",
        "6-9",
        "6-9",
        "10-14",
        "10-14",
        "15-18",
        "15-18",
        "19-23",
        "19-23",
    ]


@pytest.mark.unit
def test_fit_recovers_pedestrian_dark_and_wet_effects() -> None:
    counts, _ = _synthetic(dark_mult=3.0, wet_mult=1.5)

    model = fit_temporal(counts, alpha=1e-4)

    effects = model.pedestrian_effects()
    assert effects["dark"] == pytest.approx(3.0, rel=0.25)
    assert effects["wet"] == pytest.approx(1.5, rel=0.25)


@pytest.mark.unit
def test_multipliers_average_to_one_over_exposure() -> None:
    counts, exposure = _synthetic(dark_mult=3.0, wet_mult=1.5, seed=1)
    model = fit_temporal(counts, alpha=1e-4)

    mult = model.normalized_multiplier(exposure)

    for _, grp in exposure.assign(m=mult).groupby("road_group"):
        assert np.average(grp["m"], weights=grp["hours"]) == pytest.approx(1.0, rel=1e-6)


@pytest.mark.unit
def test_contributions_sum_to_log_multiplier() -> None:
    counts, exposure = _synthetic(dark_mult=2.0, wet_mult=1.2, seed=2)
    model: TemporalModel = fit_temporal(counts, alpha=1e-3)
    cells = exposure.head(20)

    contrib = model.log_contributions(cells, reference=exposure)
    log_mult = np.log(model.normalized_multiplier(cells, reference=exposure))

    assert contrib.sum(axis=1).to_numpy() == pytest.approx(log_mult.to_numpy(), abs=1e-9)
    assert set(CELL_KEYS) <= set(exposure.columns)
