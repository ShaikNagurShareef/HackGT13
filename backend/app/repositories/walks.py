"""Shared walks in MongoDB Atlas (collection `shared_walks`).

One small document per walk, keyed by an unguessable walk_id and deleted by a TTL index six
hours after its last update. Updates are conditional on the previous `updated_at`, so two
racing position posts cannot overwrite each other. Like the reports repository: tight
timeouts, a short cooldown after a failure, and no I/O until first use. Failures raise
WalksUnavailableError, which the service turns into a friendly 503.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, AsyncMongoClient, IndexModel, ReturnDocument
from pymongo.errors import PyMongoError

from app.domain.walks import WALK_STATUSES, Destination, SharedWalk, WalkPosition, WalkStatus
from app.repositories.reports import (
    COOLDOWN_S,
    OPERATION_TIMEOUT_MS,
    SERVER_SELECTION_TIMEOUT_MS,
    tls_options,
)

log = logging.getLogger(__name__)

COLLECTION = "shared_walks"
PROJECTION = {"_id": 0}
INDEXES = (
    IndexModel([("walk_id", ASCENDING)], name="walk_id_unique", unique=True),
    IndexModel([("expires_at", ASCENDING)], name="expires_at_ttl", expireAfterSeconds=0),
)
INDEX_NAMES = tuple(str(model.document["name"]) for model in INDEXES)
MUTABLE_FIELDS = ("status", "eta_at", "position", "updated_at", "expires_at")


class WalksUnavailableError(Exception):
    """Atlas is unconfigured, unreachable, or cooling down after a failure."""


def _as_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("expected a datetime")
    return value


def _as_status(value: object) -> WalkStatus:
    if value not in WALK_STATUSES:
        raise ValueError("unknown walk status")
    return value  # type: ignore[return-value]  # checked against the Literal's values


def _parse_position(raw: Mapping[str, Any] | None) -> WalkPosition | None:
    if raw is None:
        return None
    accuracy = raw.get("accuracy_m")
    return WalkPosition(
        lat=float(raw["lat"]),
        lon=float(raw["lon"]),
        accuracy_m=float(accuracy) if accuracy is not None else None,
        at=_as_datetime(raw["at"]),
    )


def _parse_route(raw: object) -> tuple[tuple[float, float], ...] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise TypeError("route must be a list")
    return tuple((float(lon), float(lat)) for lon, lat in raw)


def parse_walk(doc: Mapping[str, Any]) -> SharedWalk | None:
    """Documents come from the network: validate each one and skip anything malformed."""
    try:
        dest = doc["destination"]
        return SharedWalk(
            walk_id=str(doc["walk_id"]),
            token_hash=str(doc["token_hash"]),
            status=_as_status(doc["status"]),
            destination=Destination(str(dest["label"]), float(dest["lat"]), float(dest["lon"])),
            eta_at=_as_datetime(doc["eta_at"]),
            position=_parse_position(doc.get("position")),
            route=_parse_route(doc.get("route")),
            created_at=_as_datetime(doc["created_at"]),
            updated_at=_as_datetime(doc["updated_at"]),
            expires_at=_as_datetime(doc["expires_at"]),
        )
    except (KeyError, TypeError, ValueError):
        log.warning("skipping malformed shared walk")
        return None


def _position_doc(position: WalkPosition | None) -> dict[str, Any] | None:
    if position is None:
        return None
    return {
        "lat": position.lat,
        "lon": position.lon,
        "accuracy_m": position.accuracy_m,
        "at": position.at,
    }


def walk_doc(walk: SharedWalk) -> dict[str, Any]:
    dest = walk.destination
    return {
        "walk_id": walk.walk_id,
        "token_hash": walk.token_hash,
        "status": walk.status,
        "destination": {"label": dest.label, "lat": dest.lat, "lon": dest.lon},
        "eta_at": walk.eta_at,
        "position": _position_doc(walk.position),
        "route": [[lon, lat] for lon, lat in walk.route] if walk.route is not None else None,
        "created_at": walk.created_at,
        "updated_at": walk.updated_at,
        "expires_at": walk.expires_at,
    }


class WalksRepository:
    def __init__(
        self,
        uri: str | None,
        db_name: str = "pathpulse",
        *,
        collection: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._uri = uri
        self._db_name = db_name
        self._coll: Any | None = collection
        self._client: AsyncMongoClient[dict[str, Any]] | None = None
        self._clock = clock
        self._down_until = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._uri) or self._coll is not None

    def _failed(self, op: str, exc: Exception) -> WalksUnavailableError:
        # Exception text can echo the connection string; log the type only.
        log.warning("shared walks %s failed: %s", op, type(exc).__name__)
        self._down_until = self._clock() + COOLDOWN_S
        return WalksUnavailableError(op)

    def _collection(self) -> Any | None:
        """The collection, or None when unconfigured or cooling down after a failure."""
        if not self.configured or self._clock() < self._down_until:
            return None
        if self._coll is None:
            uri = self._uri or ""
            try:
                self._client = AsyncMongoClient(
                    uri,
                    serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
                    connectTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
                    timeoutMS=OPERATION_TIMEOUT_MS,
                    tz_aware=True,
                    appname="pathpulse",
                    **tls_options(uri),
                )
            except PyMongoError as exc:  # e.g. InvalidURI
                self._failed("connect", exc)
                return None
            self._coll = self._client[self._db_name][COLLECTION]
        return self._coll

    def _require(self) -> Any:
        coll = self._collection()
        if coll is None:
            raise WalksUnavailableError("unavailable")
        return coll

    async def ensure_indexes(self) -> bool:
        coll = self._collection()
        if coll is None:
            return False
        try:
            await coll.create_indexes(list(INDEXES))
        except PyMongoError as exc:
            self._failed("ensure_indexes", exc)
            return False
        return True

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def create(self, walk: SharedWalk) -> None:
        coll = self._require()
        try:
            await coll.insert_one(walk_doc(walk))
        except PyMongoError as exc:
            raise self._failed("create", exc) from exc

    async def get(self, walk_id: str, now: datetime) -> SharedWalk | None:
        """The walk, or None when it never existed or has expired (TTL deletion can lag)."""
        coll = self._require()
        try:
            doc = await coll.find_one({"walk_id": walk_id, "expires_at": {"$gt": now}}, PROJECTION)
        except PyMongoError as exc:
            raise self._failed("get", exc) from exc
        return parse_walk(doc) if doc is not None else None

    async def save_update(self, previous: SharedWalk, updated: SharedWalk) -> SharedWalk | None:
        """Write `updated` only if nobody changed the walk since `previous` was read."""
        coll = self._require()
        doc = walk_doc(updated)
        query = {"walk_id": previous.walk_id, "updated_at": previous.updated_at}
        change = {"$set": {field: doc[field] for field in MUTABLE_FIELDS}}
        try:
            saved = await coll.find_one_and_update(
                query,
                change,
                upsert=False,
                return_document=ReturnDocument.AFTER,
                projection=PROJECTION,
            )
        except PyMongoError as exc:
            raise self._failed("save_update", exc) from exc
        return parse_walk(saved) if saved is not None else None
