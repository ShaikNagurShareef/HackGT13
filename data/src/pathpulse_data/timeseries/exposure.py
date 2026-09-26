"""Light, wet, and day-group definitions shared by crash rows and exposure hours.

Using one definition for both the numerator (crashes) and the denominator (hours)
keeps the temporal model's multipliers unbiased.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

import pandas as pd
from astral import Observer
from astral.sun import elevation

from pathpulse_data.config import CITY_LAT, CITY_LON, THRESHOLDS

OBSERVER = Observer(latitude=CITY_LAT, longitude=CITY_LON)
SUNRISE_ELEVATION_DEG = -0.833
CIVIL_TWILIGHT_DEG = -6.0
FRIDAY, SATURDAY, SUNDAY = 4, 5, 6


class Light(StrEnum):
    DAY = "day"
    TWILIGHT = "twilight"
    DARK = "dark"


class DayGroup(StrEnum):
    WEEKDAY = "weekday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


def light_at(ts: datetime) -> Light:
    """Classify a timezone-aware instant by solar elevation at the coverage centroid."""
    elev = elevation(OBSERVER, ts)
    if elev > SUNRISE_ELEVATION_DEG:
        return Light.DAY
    if elev > CIVIL_TWILIGHT_DEG:
        return Light.TWILIGHT
    return Light.DARK


def day_group(ts: datetime) -> DayGroup:
    wd = ts.weekday()
    if wd == FRIDAY:
        return DayGroup.FRIDAY
    if wd == SATURDAY:
        return DayGroup.SATURDAY
    if wd == SUNDAY:
        return DayGroup.SUNDAY
    return DayGroup.WEEKDAY


def wet_flags(precip_mm: pd.Series, threshold_mm: float = THRESHOLDS.wet_precip_mm) -> pd.Series:
    """Wet if precipitation >= threshold in the current or the previous hour."""
    now = precip_mm.fillna(0.0) >= threshold_mm
    prev = now.shift(1, fill_value=False)
    return (now | prev).astype(bool)


def annotate_hours(weather: pd.DataFrame) -> pd.DataFrame:
    """Add hour, day_group, light, wet to an hourly weather frame with tz-aware `time`."""
    times = pd.to_datetime(weather["time"])
    # Solar elevation at mid-hour represents the hour better than its start.
    mids = times + pd.Timedelta(minutes=30)
    return weather.assign(
        hour=times.dt.hour,
        day_group=[day_group(t).value for t in times],
        light=[light_at(t.to_pydatetime()).value for t in mids],
        wet=wet_flags(weather["precip_mm"]),
    )


def exposure_cells(weather: pd.DataFrame) -> pd.DataFrame:
    """Hours of exposure per (day_group, hour, light, wet) cell."""
    hours = annotate_hours(weather)
    return (
        hours.groupby(["day_group", "hour", "light", "wet"], observed=True)
        .size()
        .rename("hours")
        .reset_index()
    )
