"""Per-client sliding-window rate limits (NFR-11) without extra services.

- General limit is generous: at the expo, every judge shares one venue NAT address.
- Paid endpoints (/explain, /geocode, /tts, POST /imagine) and writes (POST /reports,
  POST /walks) get a tighter per-client limit. Rules are method-aware: the map reads
  GET /reports on every pan, so viewing reports stays on the general limit.
- The client key is `request.client.host`, which uvicorn's --proxy-headers sets from Caddy's
  X-Forwarded-For only for trusted proxies, so raw headers cannot spoof it.
- State lives in a bounded TTL cache so rotating addresses cannot exhaust memory.
"""

from __future__ import annotations

import ipaddress
import time
from collections import deque

from cachetools import TTLCache
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

WINDOW_S = 60.0
MAX_CLIENTS = 50_000
EXEMPT_PREFIXES = ("/healthz", "/static")
ANY_METHOD = "*"
PAID_RULES: tuple[tuple[str, str], ...] = (
    (ANY_METHOD, "/explain"),
    (ANY_METHOD, "/geocode"),
    (ANY_METHOD, "/tts"),
    ("POST", "/imagine"),  # Grok Imagine generation; GET only serves already-cached images
    ("POST", "/reports"),
    ("POST", "/walks"),  # starting a shared walk
    # PUT position stays on the general limit (one venue NAT, ~12/min per walker); an in-memory
    # per-walk gate in services/walks.py rejects floods before they reach Mongo.
)
IPV6_PREFIX = 64


def is_paid(method: str, path: str) -> bool:
    """True when this request counts against the tighter paid/write limit."""
    return any(
        path.startswith(prefix) and rule in (ANY_METHOD, method.upper())
        for rule, prefix in PAID_RULES
    )


def client_key(host: str | None) -> str:
    """IPv4 as-is; IPv6 grouped by /64 so one household cannot rotate past the limit."""
    if not host:
        return "unknown"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/{IPV6_PREFIX}", strict=False))
    return str(ip)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, per_minute: int, paid_per_minute: int) -> None:
        super().__init__(app)
        self.per_minute = per_minute
        self.paid_per_minute = paid_per_minute
        self._hits: TTLCache[str, deque[float]] = TTLCache(maxsize=MAX_CLIENTS, ttl=WINDOW_S)

    def _allow(self, key: str, limit: int, now: float) -> bool:
        hits = self._hits.get(key)
        if hits is None:
            hits = deque()
        while hits and now - hits[0] > WINDOW_S:
            hits.popleft()
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)
        client = client_key(request.client.host if request.client else None)
        now = time.monotonic()
        allowed = self._allow(client, self.per_minute, now)
        if allowed and is_paid(request.method, path):
            allowed = self._allow(f"paid:{client}", self.paid_per_minute, now)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "data": None,
                    "model_version": None,
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Try again in a minute.",
                    },
                },
            )
        return await call_next(request)
