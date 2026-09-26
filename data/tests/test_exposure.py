"""Shared light/wet/day-group definitions for crashes and exposure hours."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from pathpulse_data.config import TZ
from pathpulse_data.timeseries.exposure import (
    DayGroup,
    Light,
    day_group,
    exposure_cells,
    light_at,
    wet_flags,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("iso", "expected"),
    [
        ("2026-09-25T13:00", Light.DAY),
        ("2026-09-25T23:00", Light.DARK),
        ("2026-09-25T03:00", Light.DARK),
        ("2026-09-25T19:50", Light.TWILIGHT),  # sunset ~19:32 EDT in late September
        ("2026-12-21T17:15", Light.DAY),  # before sunset ~17:36 EST
        ("2026-12-21T17:50", Light.TWILIGHT),  # between sunset and civil dusk ~18:03
        ("2026-12-21T18:30", Light.DARK),
    ],
)
def test_light_at(iso: str, expected: Light) -> None:
    ts = datetime.fromisoformat(iso).replace(tzinfo=TZ)
    assert light_at(ts) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("iso", "group"),
    [
        ("2026-09-21T10:00", DayGroup.WEEKDAY),  # Monday
        ("2026-09-24T10:00", DayGroup.WEEKDAY),  # Thursday
        ("2026-09-25T10:00", DayGroup.FRIDAY),
        ("2026-09-26T10:00", DayGroup.SATURDAY),
        ("2026-09-27T10:00", DayGroup.SUNDAY),
    ],
)
def test_day_group(iso: str, group: DayGroup) -> None:
    assert day_group(datetime.fromisoformat(iso)) is group


@pytest.mark.unit
def test_wet_flags_include_previous_hour() -> None:
    precip = pd.Series([0.0, 0.5, 0.0, 0.0, 0.05, 0.2])

    wet = wet_flags(precip, threshold_mm=0.1)

    assert wet.tolist() == [False, True, True, False, False, True]


@pytest.mark.unit
def test_exposure_cells_count_hours_per_cell() -> None:
    idx = pd.date_range("2026-09-21 00:00", periods=48, freq="h", tz=TZ)
    weather = pd.DataFrame({"time": idx, "precip_mm": [0.0] * 24 + [1.0] * 24})

    cells = exposure_cells(weather)

    assert cells["hours"].sum() == 48
    assert set(cells.columns) >= {"day_group", "hour", "light", "wet", "hours"}
    wet_hours = cells.loc[cells["wet"], "hours"].sum()
    assert wet_hours == 24  # Tue all-wet; Mon 23:00->Tue 00:00 prev-hour carry is Tue itself
