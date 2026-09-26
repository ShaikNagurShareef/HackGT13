"""Live conditions from Open-Meteo with caching and honest fallbacks (COND-01..04, EC-20/21/24)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.domain.timeutil import ATLANTA

log = logging.getLogger(__name__)
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
LAT, LON = 33.7756, -84.3963
CACHE_TTL_S = 600.0
STALE_OK_S = 3600.0
WET_MM = 0.1
FORECAST_HOURS = 48
FROZEN_CODES = frozenset({56, 57, 66, 67, 71, 73, 75, 77, 85, 86})


@dataclass(frozen=True)
class HourForecast:
    time: datetime
    precip_mm: float
    code: int

    @property
    def wet(self) -> bool:
        return self.precip_mm >= WET_MM or self.code in FROZEN_CODES


@dataclass(frozen=True)
class Forecast:
    fetched_at: float
    hours: tuple[HourForecast, ...]

    def at(self, ts: datetime) -> HourForecast | None:
        key = ts.astimezone(ATLANTA).replace(minute=0, second=0, microsecond=0)
        return next((h for h in self.hours if h.time == key), None)


@dataclass(frozen=True)
class Resolved:
    wet: bool
    source: str  # live | override | assumed
    label: str


class WeatherService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._cache: Forecast | None = None

    async def forecast(self) -> Forecast | None:
        now = time.monotonic()
        if self._cache and now - self._cache.fetched_at < CACHE_TTL_S:
            return self._cache
        try:
            fresh = await self._fetch()
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("open-meteo unavailable: %s", type(exc).__name__)
            stale_ok = self._cache and now - self._cache.fetched_at < STALE_OK_S
            return self._cache if stale_ok else None
        self._cache = fresh
        return fresh

    async def _fetch(self) -> Forecast:
        params = {
            "latitude": LAT,
            "longitude": LON,
            "hourly": "precipitation,weather_code",
            "timezone": "America/New_York",
            "forecast_hours": FORECAST_HOURS,
            "past_hours": 1,
        }
        resp = await self._client.get(FORECAST_URL, params=params, timeout=4.0)
        resp.raise_for_status()
        hourly = resp.json()["hourly"]
        hours = tuple(
            HourForecast(
                datetime.fromisoformat(t).replace(tzinfo=ATLANTA), float(p or 0.0), int(c or 0)
            )
            for t, p, c in zip(
                hourly["time"], hourly["precipitation"], hourly["weather_code"], strict=True
            )
        )
        return Forecast(fetched_at=time.monotonic(), hours=hours)

    async def resolve(self, cond: str, at: datetime) -> Resolved:
        if cond in ("dry", "wet"):
            return Resolved(cond == "wet", "override", f"{cond.title()} (your choice)")
        forecast = await self.forecast()
        if forecast is None:
            return Resolved(False, "assumed", "Live weather unavailable — using dry conditions.")
        hour = forecast.at(at)
        if hour is None:
            return Resolved(False, "assumed", "Assuming dry — no forecast for this time.")
        if hour.code in FROZEN_CODES:
            return Resolved(
                True, "live", "Icy conditions are rarer in our data — use extra caution."
            )
        label = "Rain" if hour.wet else "Dry"
        return Resolved(hour.wet, "live", f"{label} · live forecast")
