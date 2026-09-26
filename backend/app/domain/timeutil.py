"""Atlanta-local time: departures, day groups, and light (PRD COND-03, EC-22, EC-25).

Definitions mirror the data pipeline (timeseries/exposure.py) so a cell here means exactly
what the model was trained on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import elevation

ATLANTA = ZoneInfo("America/New_York")
OBSERVER = Observer(latitude=33.7756, longitude=-84.3963)
SUNRISE_ELEVATION_DEG = -0.833
CIVIL_TWILIGHT_DEG = -6.0
MAX_DEPARTURE_OFFSET = timedelta(days=400)
_RELATIVE = re.compile(r"^\+(\d{1,3})([mh])$")
_DAY_GROUPS = {4: "friday", 5: "saturday", 6: "sunday"}


@dataclass(frozen=True)
class Cell:
    day_group: str
    hour: int
    light: str
    wet: bool

    @property
    def key(self) -> tuple[str, int, str, bool]:
        return (self.day_group, self.hour, self.light, self.wet)


def now_atlanta() -> datetime:
    return datetime.now(ATLANTA)


def parse_departure(value: str, now: datetime | None = None) -> datetime:
    """'now', '+15m', '+1h', or ISO-8601 (naive ISO is Atlanta wall-clock time)."""
    current = now or now_atlanta()
    text = value.strip().lower()
    if text == "now":
        return current
    match = _RELATIVE.match(text)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        return current + (timedelta(minutes=amount) if unit == "m" else timedelta(hours=amount))
    try:
        parsed = datetime.fromisoformat(value.strip())
        local = (
            parsed.replace(tzinfo=ATLANTA) if parsed.tzinfo is None else parsed.astimezone(ATLANTA)
        )
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"invalid departure time: {value!r}") from exc
    if abs(local - current) > MAX_DEPARTURE_OFFSET:
        raise ValueError(f"departure too far from now: {value!r}")
    return local


def day_group(ts: datetime) -> str:
    return _DAY_GROUPS.get(ts.weekday(), "weekday")


def light_at(ts: datetime) -> str:
    elev = elevation(OBSERVER, ts)
    if elev > SUNRISE_ELEVATION_DEG:
        return "day"
    if elev > CIVIL_TWILIGHT_DEG:
        return "twilight"
    return "dark"


def cell_at(ts: datetime, wet: bool) -> Cell:
    local = ts.astimezone(ATLANTA)
    return Cell(day_group=day_group(local), hour=local.hour, light=light_at(local), wet=wet)
