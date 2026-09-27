"""Spoken navigation alerts (VOX-02) through the same voice chain as explanations.

The client names a cached route, which of its two routes it follows, and the alert's index;
the line itself is written here from the route's own alert stretches, so no client text is
ever spoken. Distance to the stretch changes as the person moves, so it stays on the client.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from cachetools import LRUCache

from app.api.envelope import AppError
from app.api.schemas import AlertOut, RouteOut, RoutesData
from app.services.explain.evidence import _clean
from app.services.tts import VoiceChain

AlertKind = Literal["pp", "fast"]
ALERT_LEAD = "High traffic risk ahead."
MAX_ALERT_NAMES = 3  # merged stretches can name several streets; three keep the line short
ALERT_AUDIO_CACHE_SIZE = 512


def followed_route(routes: RoutesData, kind: AlertKind) -> RouteOut:
    """The route the client navigates: PathPro when asked for and present, else the fastest."""
    if kind == "pp" and routes.pathpro is not None:
        return routes.pathpro
    return routes.fastest


def alert_text(alert: AlertOut) -> str:
    """The spoken line, e.g. "High traffic risk ahead. Spring Street." (names cleaned, capped)."""
    names = [name for name in (_clean(n) for n in alert.names) if name][:MAX_ALERT_NAMES]
    if not names:
        return ALERT_LEAD
    return f"{ALERT_LEAD} {' and '.join(names)}."


def resolve_alert_text(
    cache: Mapping[str, RoutesData], route_key: str, kind: AlertKind, index: int
) -> str:
    """The alert line for one stretch; 404 ROUTE_EXPIRED or ALERT_NOT_FOUND otherwise."""
    routes = cache.get(route_key)
    if routes is None:
        raise AppError("ROUTE_EXPIRED", "Route details expired. Request the route again.", 404)
    alerts = followed_route(routes, kind).alerts
    if not 0 <= index < len(alerts):
        raise AppError("ALERT_NOT_FOUND", "That alert is not on this route.", 404)
    return alert_text(alerts[index])


class AlertAudio:
    """Alert audio cached per (route, kind, index, voice); silence is never cached."""

    def __init__(self, voices: VoiceChain, maxsize: int = ALERT_AUDIO_CACHE_SIZE) -> None:
        self._voices = voices
        self._cache: LRUCache[tuple[str, str, int, str], bytes] = LRUCache(maxsize=maxsize)

    async def speak(self, route_key: str, kind: AlertKind, index: int, text: str) -> bytes | None:
        key = (route_key, kind, index, self._voices.voice_key)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        audio = await self._voices.speak(text)
        if audio is not None:
            self._cache[key] = audio
        return audio
