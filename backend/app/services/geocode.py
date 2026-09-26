"""Address autocomplete via Geoapify, server-side so the key never reaches the browser."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from cachetools import TTLCache

log = logging.getLogger(__name__)
AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
CITY_RECT = "rect:-84.56,33.64,-84.28,33.89"
BIAS = "proximity:-84.3905,33.7765"
MAX_RESULTS = 5


@dataclass(frozen=True)
class GeoResult:
    label: str
    address: str
    lat: float
    lon: float


class GeocodeService:
    def __init__(self, client: httpx.AsyncClient, api_key: str | None) -> None:
        self._client = client
        self._key = api_key
        self._cache: TTLCache[str, tuple[GeoResult, ...]] = TTLCache(maxsize=2048, ttl=3600)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def search(self, query: str) -> tuple[GeoResult, ...]:
        q = " ".join(query.split())[:80]
        if len(q) < 3 or not self._key:
            return ()
        cached = self._cache.get(q.lower())
        if cached is not None:
            return cached
        params = {
            "text": q,
            "filter": CITY_RECT,
            "bias": BIAS,
            "limit": MAX_RESULTS,
            "format": "json",
            "apiKey": self._key,
        }
        try:
            resp = await self._client.get(AUTOCOMPLETE_URL, params=params, timeout=2.5)
            resp.raise_for_status()
            rows = resp.json().get("results", [])
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("geocode failed: %s", type(exc).__name__)
            return ()
        results = tuple(
            GeoResult(
                label=str(r.get("name") or r.get("address_line1") or r.get("formatted", "")),
                address=str(r.get("address_line2") or r.get("formatted", "")),
                lat=float(r["lat"]),
                lon=float(r["lon"]),
            )
            for r in rows
            if "lat" in r and "lon" in r
        )
        self._cache[q.lower()] = results
        return results
