"""Crash history from Tiger Data continuous aggregates, with tight timeouts (never on the hot path).

If the database is unset, slow, or down, callers get None and the UI simply hides the chart.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg

log = logging.getLogger(__name__)
CONNECT_TIMEOUT_S = 3
STATEMENT_TIMEOUT_MS = 800
HOURS = 24

HOURLY_SQL = """
SELECT extract(hour FROM bucket AT TIME ZONE 'America/New_York')::int AS hour,
       coalesce(sum(crashes), 0)::float8 AS crashes,
       coalesce(sum(ped_crashes), 0)::float8 AS ped_crashes
FROM crashes_hourly
WHERE seg_id = %s
GROUP BY 1
"""


@dataclass(frozen=True)
class HourlyProfile:
    crashes: tuple[float, ...]
    ped_crashes: tuple[float, ...]


class HistoryRepository:
    def __init__(self, database_url: str | None) -> None:
        self._url = database_url

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def _connect(self) -> psycopg.AsyncConnection:
        assert self._url is not None
        conn = await psycopg.AsyncConnection.connect(
            self._url, connect_timeout=CONNECT_TIMEOUT_S, autocommit=True
        )
        await conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        return conn

    async def ping(self) -> str:
        if not self._url:
            return "not_configured"
        try:
            async with await self._connect() as conn:
                await conn.execute("SELECT 1")
            return "ok"
        except psycopg.Error as exc:
            log.warning("database ping failed: %s", type(exc).__name__)
            return "unavailable"

    async def hourly(self, seg_id: int) -> HourlyProfile | None:
        if not self._url:
            return None
        try:
            async with await self._connect() as conn:
                cur = await conn.execute(HOURLY_SQL, (seg_id,))
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            log.warning("hourly history failed: %s", type(exc).__name__)
            return None
        crashes, peds = [0.0] * HOURS, [0.0] * HOURS
        for hour, total, ped in rows:
            crashes[int(hour)], peds[int(hour)] = float(total), float(ped)
        return HourlyProfile(tuple(crashes), tuple(peds))
