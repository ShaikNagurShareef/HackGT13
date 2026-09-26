"""Per-IP sliding-window rate limit (NFR-11: 60 requests/min/IP) without extra services."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

WINDOW_S = 60.0
EXEMPT_PREFIXES = ("/healthz", "/static")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, per_minute: int) -> None:
        super().__init__(app)
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)
        client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        now = time.monotonic()
        hits = self._hits[client]
        while hits and now - hits[0] > WINDOW_S:
            hits.popleft()
        if len(hits) >= self.per_minute:
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
        hits.append(now)
        return await call_next(request)
