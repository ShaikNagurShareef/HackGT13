"""Benchmark table vs baselines, and temporal cell tables / holdout evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.config import TZ
from pathpulse_data.export.assemble import reference_dates
from pathpulse_data.model import benchmark as bench
from pathpulse_data.model.temporal_data import cell_table, evaluate_temporal, flat_baseline
from pathpulse_data.timeseries.exposure import annotate_hours

from tests.conftest import N_SEG


@pytest.mark.integration
def test_benchmark_reports_every_method_and_beats_random(
    fitted: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, _, fit = fitted
    monkeypatch.setattr(bench, "hin_scores", lambda d: pd.Series(0.0, index=d.features.index))
    monkeypatch.setattr(bench, "BOOT_REPS", 30)

    result = bench.benchmark(fit, data, 2023)

    methods = {m["method"]: m for m in result["methods"]}
    assert len(methods) == 6
    ours = methods["PathPulse (EB ensemble)"]["capture_top10"]
    assert ours > methods["Random"]["capture_top10"]
    lo, hi = result["capture_top10_ci95"]
    assert lo <= ours <= hi
    assert len(result["calibration"]) == 10
    assert N_SEG > 0


def _hours(years: tuple[int, ...]) -> pd.DataFrame:
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31 23:00", freq="h", tz=TZ)
    rng = np.random.default_rng(0)
    weather = pd.DataFrame(
        {"time": idx, "precip_mm": rng.choice([0.0, 1.0], len(idx), p=[0.85, 0.15])}
    )
    hours = annotate_hours(weather)
    return hours.assign(year=hours["time"].dt.year)


def _crashes(hours: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Crashes whose pedestrian rate triples in darkness."""
    rng = np.random.default_rng(seed)
    base = np.where(hours["light"] == "dark", 3.0, 1.0) * 0.004
    rows = []
    for rg, scale in (("arterial", 3.0), ("collector", 1.5), ("local", 1.0)):
        for is_ped, mult in ((False, 10.0), (True, 1.0)):
            n = rng.poisson(base * scale * mult)
            picked = hours.loc[n > 0]
            rows.append(picked.assign(weight=n[n > 0].astype(float), is_ped=is_ped, road_group=rg))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def temporal_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    hours = _hours((2019, 2020, 2021))
    return hours, _crashes(hours, seed=1)


@pytest.mark.integration
def test_cell_table_conserves_hours_and_counts(temporal_inputs: tuple) -> None:
    hours, crashes = temporal_inputs

    table = cell_table(crashes, hours, range(2019, 2021))

    n_hours = int(hours["year"].isin([2019, 2020]).sum())
    per_group = table.groupby(["road_group", "is_ped"])["hours"].sum()
    assert (per_group == n_hours).all()
    in_window = crashes["year"].isin([2019, 2020])
    assert table["count"].sum() == pytest.approx(crashes.loc[in_window, "weight"].sum())


@pytest.mark.integration
def test_flat_baseline_preserves_group_totals(temporal_inputs: tuple) -> None:
    hours, crashes = temporal_inputs
    table = cell_table(crashes, hours, range(2019, 2021))

    flat = flat_baseline(table, table)

    assert flat.sum() == pytest.approx(table["count"].sum())


@pytest.mark.integration
def test_temporal_model_beats_flat_on_holdout(temporal_inputs: tuple) -> None:
    hours, crashes = temporal_inputs

    result = evaluate_temporal(crashes, hours, range(2019, 2021), range(2021, 2022))

    assert result["deviance_reduction"] > 0
    assert result["effect_dark"] == pytest.approx(3.0, rel=0.35)


@pytest.mark.unit
def test_reference_dates_cover_every_day_group() -> None:
    from datetime import date

    refs = reference_dates(date(2026, 9, 25))  # a Friday

    assert refs == {
        "friday": date(2026, 9, 25),
        "saturday": date(2026, 9, 26),
        "sunday": date(2026, 9, 27),
        "weekday": date(2026, 9, 28),
    }


@pytest.mark.unit
def test_hour_start_handles_repeated_fall_back_hour() -> None:
    from pathpulse_data.model.temporal_data import hour_start

    # 2023-11-05 01:30 EDT and 01:30 EST are different instants in the repeated hour.
    ts = pd.Series(pd.to_datetime(["2023-11-05T05:30:00Z", "2023-11-05T06:30:00Z"], utc=True))

    out = hour_start(ts)

    assert [t.hour for t in out] == [1, 1]
    assert out.iloc[0] != out.iloc[1]
    assert str(out.iloc[0].tz) == "America/New_York"
