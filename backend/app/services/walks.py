"""Share my walk: create a followable walk, apply owner-only position updates, read for followers.

- walk_id: 128 random bits, URL-safe; anyone with the follow link can read the walk.
- owner_token: 256 random bits, returned once; only its SHA-256 is stored and it is compared
  in constant time. Responses never include the token or its hash.
- Position updates are throttled per walk (one per 3 s) except status changes, and ignored
  once the walk has ended. Coordinates must fall in a generous metro-Atlanta box.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from cachetools import TTLCache

from app.api.envelope import AppError
from app.api.walk_schemas import (
    CreatedWalkOut,
    CreateWalkRequest,
    DestinationOut,
    PositionOut,
    PositionUpdateRequest,
    WalkOut,
    WalkSummaryOut,
)
from app.domain.walks import (
    MIN_UPDATE_INTERVAL,
    WALK_TTL,
    Destination,
    SharedWalk,
    WalkPosition,
    in_atlanta,
)
from app.repositories.walks import WalksRepository, WalksUnavailableError

Clock = Callable[[], datetime]

WALK_ID_BYTES = 16  # 128 bits -> 22 URL-safe characters
OWNER_TOKEN_BYTES = 32  # 256 bits -> 43 URL-safe characters
WALK_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}")
FOLLOW_PREFIX = "/follow/"


def utcnow() -> datetime:
    """Millisecond precision, matching what MongoDB stores, so conditional updates compare."""
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def unavailable() -> AppError:
    return AppError(
        "WALKS_UNAVAILABLE",
        "Live sharing is unavailable right now. Navigation still works.",
        status=503,
    )


def not_found() -> AppError:
    return AppError(
        "WALK_NOT_FOUND", "This shared walk has ended or the link has expired.", status=404
    )


def forbidden() -> AppError:
    return AppError("WALK_FORBIDDEN", "Only the walker can update this shared walk.", status=403)


def throttled() -> AppError:
    return AppError(
        "WALK_THROTTLED",
        "Updates are arriving quickly; the next one will go through in a moment.",
        status=429,
    )


def outside_area() -> AppError:
    return AppError("OUTSIDE_AREA", "Live sharing works around Atlanta only.", status=422)


def _eta_s(walk: SharedWalk, now: datetime) -> int:
    if walk.status != "walking":
        return 0
    return max(0, round((walk.eta_at - now).total_seconds()))


def _position_out(position: WalkPosition | None) -> PositionOut | None:
    if position is None:
        return None
    return PositionOut(
        lat=position.lat, lon=position.lon, accuracy_m=position.accuracy_m, at=position.at
    )


def summary_out(walk: SharedWalk, now: datetime) -> WalkSummaryOut:
    dest = walk.destination
    return WalkSummaryOut(
        walk_id=walk.walk_id,
        status=walk.status,
        destination=DestinationOut(label=dest.label, lat=dest.lat, lon=dest.lon),
        eta_s=_eta_s(walk, now),
        eta_at=walk.eta_at,
        position=_position_out(walk.position),
        updated_at=walk.updated_at,
        expires_at=walk.expires_at,
    )


def walk_out(walk: SharedWalk, now: datetime) -> WalkOut:
    route = list(walk.route) if walk.route is not None else None
    return WalkOut(**summary_out(walk, now).model_dump(), route=route)


def _check_area(req: CreateWalkRequest) -> None:
    points = [(req.destination.lon, req.destination.lat), *(req.route or [])]
    if not all(in_atlanta(lat, lon) for lon, lat in points):
        raise outside_area()


async def create_walk(
    repo: WalksRepository, req: CreateWalkRequest, now: datetime
) -> CreatedWalkOut:
    _check_area(req)
    token = secrets.token_urlsafe(OWNER_TOKEN_BYTES)
    dest = req.destination
    walk = SharedWalk(
        walk_id=secrets.token_urlsafe(WALK_ID_BYTES),
        token_hash=hash_token(token),
        status="walking",
        destination=Destination(label=dest.label, lat=dest.lat, lon=dest.lon),
        eta_at=now + timedelta(seconds=req.eta_s),
        position=None,
        route=tuple(req.route) if req.route is not None else None,
        created_at=now,
        updated_at=now,
        expires_at=now + WALK_TTL,
    )
    try:
        await repo.create(walk)
    except WalksUnavailableError as exc:
        raise unavailable() from exc
    return CreatedWalkOut(
        walk_id=walk.walk_id,
        owner_token=token,
        follow_path=f"{FOLLOW_PREFIX}{walk.walk_id}",
        expires_at=walk.expires_at,
    )


async def _load(repo: WalksRepository, walk_id: str, now: datetime) -> SharedWalk:
    if not WALK_ID_PATTERN.fullmatch(walk_id):
        raise not_found()
    try:
        walk = await repo.get(walk_id, now)
    except WalksUnavailableError as exc:
        raise unavailable() from exc
    if walk is None:
        raise not_found()
    return walk


async def get_walk(repo: WalksRepository, walk_id: str, now: datetime) -> WalkOut:
    return walk_out(await _load(repo, walk_id, now), now)


def _too_soon(walk: SharedWalk, req: PositionUpdateRequest, now: datetime) -> bool:
    status_change = req.status is not None and req.status != walk.status
    last = walk.position.at if walk.position else None
    return not status_change and last is not None and now - last < MIN_UPDATE_INTERVAL


def _apply(walk: SharedWalk, req: PositionUpdateRequest, now: datetime) -> SharedWalk:
    eta_at = now + timedelta(seconds=req.eta_s) if req.eta_s is not None else walk.eta_at
    return replace(
        walk,
        status=req.status or walk.status,
        eta_at=eta_at,
        position=WalkPosition(lat=req.lat, lon=req.lon, accuracy_m=req.accuracy_m, at=now),
        updated_at=now,
        expires_at=now + WALK_TTL,
    )


GATE_SIZE = 10_000


class RecentUpdates:
    """Per-walk time of the last accepted update, kept in memory so rapid position posts are
    throttled before any Mongo read. Only authenticated, saved updates are recorded, so a
    stranger holding a follow link cannot throttle the walker."""

    def __init__(self) -> None:
        ttl = MIN_UPDATE_INTERVAL.total_seconds()
        self._last: TTLCache[str, datetime] = TTLCache(maxsize=GATE_SIZE, ttl=ttl)

    def too_soon(self, walk_id: str, req: PositionUpdateRequest, now: datetime) -> bool:
        last = self._last.get(walk_id)
        return req.status is None and last is not None and now - last < MIN_UPDATE_INTERVAL

    def mark(self, walk_id: str, now: datetime) -> None:
        self._last[walk_id] = now


async def update_position(
    repo: WalksRepository,
    walk_id: str,
    req: PositionUpdateRequest,
    now: datetime,
    gate: RecentUpdates | None = None,
) -> WalkSummaryOut:
    if gate is not None and gate.too_soon(walk_id, req, now):
        raise throttled()
    walk = await _load(repo, walk_id, now)
    if not token_matches(req.owner_token, walk.token_hash):
        raise forbidden()
    if walk.status == "ended":
        return summary_out(walk, now)  # a finished walk stays finished
    if not in_atlanta(req.lat, req.lon):
        raise outside_area()
    if _too_soon(walk, req, now):
        raise throttled()
    try:
        saved = await repo.save_update(walk, _apply(walk, req, now))
    except WalksUnavailableError as exc:
        raise unavailable() from exc
    if saved is None:  # another update landed between our read and write
        raise throttled()
    if gate is not None:
        gate.mark(walk_id, now)
    return summary_out(saved, now)
