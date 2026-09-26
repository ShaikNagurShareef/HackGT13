"""Day-part mapping and StreetLight activity: hourly rates, bands, and per-hex joins."""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.safety.activity import (
    ACTIVITY_BANDS,
    activity_thresholds,
    band_codes,
    code_labels,
    hex_activity,
)
from pathpulse_data.safety.dayparts import (
    DAY_PART_KEYS,
    DAY_PARTS,
    day_part_for_hour,
    daypart_rates,
)

LAT, LON = 33.7756, -84.3963


@pytest.mark.unit
@pytest.mark.parametrize(
    ("hour", "part"),
    [
        (22, "night"),
        (23, "night"),
        (0, "night"),
        (5, "night"),
        (6, "morning"),
        (11, "morning"),
        (12, "afternoon"),
        (17, "afternoon"),
        (18, "evening"),
        (21, "evening"),
    ],
)
def test_day_part_for_hour(hour: int, part: str) -> None:
    assert day_part_for_hour(hour) == part


@pytest.mark.unit
def test_day_parts_cover_every_hour_once() -> None:
    hours = [h for p in DAY_PARTS for h in p.hours]

    assert sorted(hours) == list(range(24))
    assert DAY_PART_KEYS == ("night", "morning", "afternoon", "evening")


@pytest.mark.unit
def test_day_part_for_hour_rejects_bad_hours() -> None:
    with pytest.raises(ValueError, match="hour"):
        day_part_for_hour(24)


@pytest.mark.unit
def test_daypart_rates_convert_streetlight_periods_to_hourly() -> None:
    # StreetLight daily volume per period: 1=0-6h, 2=6-10h, 3=10-15h, 4=15-19h, 5=19-24h.
    daily = pd.DataFrame({1: [60.0], 2: [40.0], 3: [50.0], 4: [40.0], 5: [50.0]})

    rates = daypart_rates(daily)

    assert list(rates.columns) == list(DAY_PART_KEYS)
    assert rates.loc[0, "morning"] == pytest.approx(10.0)  # 4h of 10/h + 2h of 10/h
    assert rates.loc[0, "night"] == pytest.approx(10.0)


@pytest.mark.unit
def test_daypart_rates_skip_missing_periods_and_null_when_none() -> None:
    daily = pd.DataFrame({1: [np.nan, np.nan], 2: [40.0, np.nan], 3: [np.nan, np.nan]})

    rates = daypart_rates(daily)

    assert rates.loc[0, "morning"] == pytest.approx(10.0)
    assert np.isnan(rates.loc[0, "night"])
    assert rates.loc[1].isna().all()


@pytest.mark.unit
def test_activity_bands_pool_all_day_parts() -> None:
    rates = pd.DataFrame(
        {"night": [1.0, 2.0, 3.0], "morning": [7.0, 8.0, 9.0], "afternoon": [10.0, 11.0, 12.0]}
    )

    lo, hi = activity_thresholds(rates)
    codes = band_codes(rates["night"].to_numpy(), (lo, hi))

    assert lo < hi
    assert list(codes) == [0, 0, 0]  # nights are quiet relative to the whole day
    assert list(code_labels(np.array([0, 1, 2, -1]))) == ["quiet", "moderate", "busy", None]
    assert ACTIVITY_BANDS == ("quiet", "moderate", "busy")


@pytest.mark.unit
def test_band_codes_mark_missing_as_unknown() -> None:
    codes = band_codes(np.array([np.nan, 5.0]), (1.0, 2.0))

    assert list(codes) == [-1, 2]
    assert codes.dtype == np.int8


@pytest.mark.unit
def test_hex_activity_averages_points_per_cell() -> None:
    cell = h3.latlng_to_cell(LAT, LON, 9)
    empty = sorted(set(h3.grid_disk(cell, 1)) - {cell})[0]
    points = pd.DataFrame(
        {"lat": [LAT, LAT], "lon": [LON, LON], "night": [2.0, 4.0], "morning": [1.0, 3.0]}
    )

    out = hex_activity(points, pd.Index([cell, empty]))

    assert out.loc[cell, "night"] == pytest.approx(3.0)
    assert out.loc[empty].isna().all()
