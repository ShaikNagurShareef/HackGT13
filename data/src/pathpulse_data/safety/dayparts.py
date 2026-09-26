"""Four day parts shared by the pipeline and the API, and StreetLight period conversion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HOURS_PER_DAY = 24


@dataclass(frozen=True)
class DayPart:
    key: str
    label: str
    hours: tuple[int, ...]


DAY_PARTS: tuple[DayPart, ...] = (
    DayPart("night", "Night (10 PM to 6 AM)", (22, 23, 0, 1, 2, 3, 4, 5)),
    DayPart("morning", "Morning (6 AM to 12 PM)", tuple(range(6, 12))),
    DayPart("afternoon", "Afternoon (12 PM to 6 PM)", tuple(range(12, 18))),
    DayPart("evening", "Evening (6 PM to 10 PM)", tuple(range(18, 22))),
)
DAY_PART_KEYS: tuple[str, ...] = tuple(p.key for p in DAY_PARTS)
_BY_HOUR = {h: p.key for p in DAY_PARTS for h in p.hours}

# StreetLight "Day_Part" periods (codes 1..5) as [start, end) hours.
STREETLIGHT_PERIODS: dict[int, tuple[int, int]] = {
    1: (0, 6),
    2: (6, 10),
    3: (10, 15),
    4: (15, 19),
    5: (19, 24),
}


def day_part_for_hour(hour: int) -> str:
    if hour not in _BY_HOUR:
        raise ValueError(f"hour must be 0..23, got {hour}")
    return _BY_HOUR[hour]


def _period_of_hour(hour: int) -> int:
    return next(p for p, (lo, hi) in STREETLIGHT_PERIODS.items() if lo <= hour < hi)


def daypart_rates(daily: pd.DataFrame) -> pd.DataFrame:
    """Daily volume per StreetLight period (columns 1..5) -> mean hourly volume per day part.

    Each hour takes its period's volume spread evenly over the period's hours. Hours whose
    period is missing are skipped; a day part with no known hour is NaN.
    """
    hourly = {}
    for hour in range(HOURS_PER_DAY):
        period = _period_of_hour(hour)
        lo, hi = STREETLIGHT_PERIODS[period]
        col = daily[period] if period in daily.columns else pd.Series(np.nan, index=daily.index)
        hourly[hour] = col.astype(float) / (hi - lo)
    by_hour = pd.DataFrame(hourly, index=daily.index)
    return pd.DataFrame(
        {p.key: by_hour[list(p.hours)].mean(axis=1, skipna=True) for p in DAY_PARTS},
        index=daily.index,
    )
