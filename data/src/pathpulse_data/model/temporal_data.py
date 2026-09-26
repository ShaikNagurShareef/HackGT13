"""Build (cell x is_ped) crash counts and exposure hours for the temporal model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pathpulse_data.config import INTERIM_DIR, RAW_DIR, TZ
from pathpulse_data.model.evaluate import poisson_deviance
from pathpulse_data.model.temporal import CELL_KEYS, TemporalModel, fit_temporal
from pathpulse_data.timeseries.exposure import annotate_hours

ROAD_GROUPS = ("arterial", "collector", "local")


def load_hours() -> pd.DataFrame:
    """Hourly frame with hour/day_group/light/wet, used for both crashes and exposure."""
    weather = pd.read_parquet(RAW_DIR / "weather_hourly.parquet")
    hours = annotate_hours(weather)
    return hours.assign(year=pd.to_datetime(hours["time"]).dt.year)


def hour_start(ts: pd.Series) -> pd.Series:
    """Start of the hour in Atlanta time, exact across DST (EC-22).

    Flooring in local time is ambiguous in the repeated fall-back hour; flooring in UTC is
    not, and every Atlanta UTC offset is a whole number of hours.
    """
    return ts.dt.tz_convert("UTC").dt.floor("h").dt.tz_convert(TZ)


def crash_cells(hours: pd.DataFrame) -> pd.DataFrame:
    """Snapped timed crashes annotated with the *same* cell definitions as exposure."""
    snaps = pd.read_parquet(INTERIM_DIR / "crash_segments.parquet")
    timed = snaps.loc[snaps["stream"] == "timed"].copy()
    segs = pd.read_parquet(
        INTERIM_DIR / "segment_features.parquet", columns=["seg_id", "road_group"]
    )
    timed = timed.merge(segs, on="seg_id")
    ts = hour_start(pd.to_datetime(timed["ts"]))
    lookup = hours.set_index(pd.to_datetime(hours["time"]))[["hour", "day_group", "light", "wet"]]
    lookup = lookup[~lookup.index.duplicated()]
    joined = lookup.reindex(ts)
    return pd.concat(
        [
            timed[["seg_id", "weight", "is_ped", "road_group", "year"]].reset_index(drop=True),
            joined.reset_index(drop=True),
        ],
        axis=1,
    ).dropna(subset=["hour"])


def cell_table(
    crashes: pd.DataFrame, hours: pd.DataFrame, years: range, by_year: bool = False
) -> pd.DataFrame:
    """Every (road_group, day_group, hour, light, wet, is_ped[, year]) cell: count and hours."""
    time_keys = ["day_group", "hour", "light", "wet"] + (["year"] if by_year else [])
    exp = (
        hours.loc[hours["year"].isin(list(years))]
        .groupby(time_keys)
        .size()
        .rename("hours")
        .reset_index()
    )
    grid = pd.concat(
        [exp.assign(road_group=rg, is_ped=ped) for rg in ROAD_GROUPS for ped in (False, True)],
        ignore_index=True,
    )
    keys = [*CELL_KEYS, "is_ped"] + (["year"] if by_year else [])
    counts = (
        crashes.loc[crashes["year"].isin(list(years))]
        .groupby(keys)["weight"]
        .sum()
        .rename("count")
        .reset_index()
    )
    grid = grid.astype({"hour": int, "wet": bool, "is_ped": bool})
    counts = counts.astype({"hour": int, "wet": bool, "is_ped": bool})
    return grid.merge(counts, on=keys, how="left").fillna({"count": 0.0})


def flat_baseline(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Rate per hour constant within (road_group, is_ped): 'time does not matter'."""
    rates = train.groupby(["road_group", "is_ped"]).apply(
        lambda g: g["count"].sum() / g["hours"].sum(), include_groups=False
    )
    keys = list(zip(test["road_group"], test["is_ped"], strict=True))
    return np.array([rates[k] for k in keys]) * test["hours"].to_numpy()


def _without_light_rain(table: pd.DataFrame) -> pd.DataFrame:
    """Collapse light and wet so a model can only learn hour, day, and road group."""
    keys = [k for k in table.columns if k not in ("light", "wet", "count", "hours")]
    agg = table.groupby(keys, as_index=False)[["count", "hours"]].sum()
    return agg.assign(light="day", wet=False)


def hour_day_baseline(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Stronger baseline: the same smoothed GLM without light or rain terms.

    Light and rain must beat this to earn their place in the model (review item #11).
    """
    model = fit_temporal(_without_light_rain(train))
    neutral = test.assign(light="day", wet=False)
    return np.exp(model.log_rate(neutral, is_ped=True)).to_numpy() * test["hours"].to_numpy()


def _shape_deviance(obs: np.ndarray, pred: np.ndarray) -> float:
    pred = np.maximum(pred, 1e-12)
    return poisson_deviance(obs, pred * obs.sum() / pred.sum())


def evaluate_temporal(
    crashes: pd.DataFrame, hours: pd.DataFrame, train_years: range, test_years: range
) -> dict[str, float]:
    train = cell_table(crashes, hours, train_years)
    test = cell_table(crashes, hours, test_years)
    model = fit_temporal(cell_table(crashes, hours, train_years, by_year=True))
    ped = test["is_ped"].to_numpy()
    pred = np.exp(model.log_rate(test.loc[ped], is_ped=True)) * test.loc[ped, "hours"]
    # Each prediction is rescaled to the test total so only the *shape* over time is compared.
    obs = test.loc[ped, "count"].to_numpy()
    dev_model = _shape_deviance(obs, pred.to_numpy())
    dev_flat = _shape_deviance(obs, flat_baseline(train, test)[ped])
    by_year = cell_table(crashes, hours, train_years, by_year=True)
    dev_hour_day = _shape_deviance(obs, hour_day_baseline(by_year, test.loc[ped]))
    return {
        "test_ped_crashes": float(obs.sum()),
        "deviance_model": dev_model,
        "deviance_flat": dev_flat,
        "deviance_hour_day": dev_hour_day,
        "deviance_reduction": 1.0 - dev_model / dev_flat,
        "deviance_reduction_vs_hour_day": 1.0 - dev_model / dev_hour_day,
        **{f"effect_{k}": v for k, v in model.pedestrian_effects().items()},
    }


def fit_final(crashes: pd.DataFrame, hours: pd.DataFrame, years: range) -> TemporalModel:
    return fit_temporal(cell_table(crashes, hours, years, by_year=True))
