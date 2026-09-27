"""Per-client daily caps shared by paid features (Grok Imagine, Ask PathPro)."""

from __future__ import annotations

from datetime import date

from cachetools import TTLCache

MAX_TRACKED_CLIENTS = 50_000
DAY_S = 86_400


class ClientDailyLimit:
    """Caps paid calls per client per day so one client cannot spend the shared budget.

    Keys are `app.middleware.client_key` values; state lives in a bounded TTL cache so rotating
    addresses cannot exhaust memory.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used: TTLCache[tuple[date, str], int] = TTLCache(
            maxsize=MAX_TRACKED_CLIENTS, ttl=DAY_S
        )

    def take(self, client: str, today: date | None = None) -> bool:
        key = (today or date.today(), client)
        used = self._used.get(key, 0)
        if used >= self._limit:
            return False
        self._used[key] = used + 1
        return True
