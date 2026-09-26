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


def crash_cells(hours: pd.DataFrame) -> pd.DataFrame:
    """Snapped timed crashes annotated with the *same* cell definitions as exposure."""
    snaps = pd.read_parquet(INTERIM_DIR / "crash_segments.parquet")
    timed = snaps.loc[snaps["stream"] == "timed"].copy()
    segs = pd.read_parquet(
        INTERIM_DIR / "segment_features.parquet", columns=["seg_id", "road_group"]
    )
    timed = timed.merge(segs, on="seg_id")
    ts = pd.to_datetime(timed["ts"]).dt.tz_convert(TZ).dt.floor("h")
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


def cell_table(crashes: pd.DataFrame, hours: pd.DataFrame, years: range) -> pd.DataFrame:
    """Every (road_group, day_group, hour, light, wet, is_ped) cell with count and hours."""
    exp = (
        hours.loc[hours["year"].isin(list(years))]
        .groupby(["day_group", "hour", "light", "wet"])
        .size()
        .rename("hours")
        .reset_index()
    )
    grid = pd.concat(
        [exp.assign(road_group=rg, is_ped=ped) for rg in ROAD_GROUPS for ped in (False, True)],
        ignore_index=True,
    )
    counts = (
        crashes.loc[crashes["year"].isin(list(years))]
        .groupby([*CELL_KEYS, "is_ped"])["weight"]
        .sum()
        .rename("count")
        .reset_index()
    )
    keys = [*CELL_KEYS, "is_ped"]
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


def evaluate_temporal(
    crashes: pd.DataFrame, hours: pd.DataFrame, train_years: range, test_years: range
) -> dict[str, float]:
    train = cell_table(crashes, hours, train_years)
    test = cell_table(crashes, hours, test_years)
    model = fit_temporal(train)
    ped = test["is_ped"].to_numpy()
    pred = np.exp(model.log_rate(test.loc[ped], is_ped=True)) * test.loc[ped, "hours"]
    # Rescale to the test total so only the *shape* over time is compared.
    obs = test.loc[ped, "count"].to_numpy()
    pred = pred.to_numpy() * obs.sum() / pred.sum()
    flat = flat_baseline(train, test)[ped]
    flat = flat * obs.sum() / flat.sum()
    dev_model, dev_flat = poisson_deviance(obs, pred), poisson_deviance(obs, flat)
    return {
        "test_ped_crashes": float(obs.sum()),
        "deviance_model": dev_model,
        "deviance_flat": dev_flat,
        "deviance_reduction": 1.0 - dev_model / dev_flat,
        **{f"effect_{k}": v for k, v in model.pedestrian_effects().items()},
    }


def fit_final(crashes: pd.DataFrame, hours: pd.DataFrame, years: range) -> TemporalModel:
    return fit_temporal(cell_table(crashes, hours, years))
