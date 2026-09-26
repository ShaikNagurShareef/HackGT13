"""Community street reports in MongoDB Atlas (collection `street_reports`).

Atlas does the work it is good at: 2dsphere viewport queries, TTL auto-expiry, one atomic
upsert per report, and a server-side aggregation for the summary. Like the Tiger Data history
repository, every call has tight timeouts; if the URI is unset, slow, or down, callers get
None / "unavailable" and the UI hides the feature. After a failure the repository skips the
network for a short cooldown so routes never wait on a dead cluster.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from typing import Any, Literal

import certifi
import pymongo
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, AsyncMongoClient, IndexModel, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.reports import CATEGORY_LABELS, REPORT_TTL, CategoryCount, StreetReport

log = logging.getLogger(__name__)

COLLECTION = "street_reports"
SERVER_SELECTION_TIMEOUT_MS = 2000
OPERATION_TIMEOUT_MS = 1500
COOLDOWN_S = 30.0
BBOX_LIMIT = 300
SEGMENT_LIMIT = 50
PROJECTION = {"_id": 0}
INDEXES = (
    IndexModel([("loc", GEOSPHERE)], name="loc_2dsphere"),
    IndexModel([("expires_at", ASCENDING)], name="expires_at_ttl", expireAfterSeconds=0),
    IndexModel(
        [("seg_id", ASCENDING), ("category", ASCENDING)], name="seg_category_unique", unique=True
    ),
)
INDEX_NAMES = tuple(str(model.document["name"]) for model in INDEXES)

Status = Literal["ok", "unavailable", "not_configured"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("expected a datetime")
    return value


def _as_category(value: object) -> str:
    if value not in CATEGORY_LABELS:
        raise ValueError("unknown report category")
    return str(value)


def parse_report(doc: Mapping[str, Any]) -> StreetReport | None:
    """Documents come from the network: validate each one and skip anything malformed."""
    try:
        lon, lat = doc["loc"]["coordinates"]
        return StreetReport(
            seg_id=int(doc["seg_id"]),
            category=_as_category(doc["category"]),
            street=str(doc["street"]),
            lon=float(lon),
            lat=float(lat),
            confirmations=int(doc["confirmations"]),
            created_at=_as_datetime(doc["created_at"]),
            updated_at=_as_datetime(doc["updated_at"]),
            expires_at=_as_datetime(doc["expires_at"]),
        )
    except (KeyError, TypeError, ValueError):
        log.warning("skipping malformed street report")
        return None


def _parse_many(docs: Iterable[Mapping[str, Any]]) -> list[StreetReport]:
    return [r for r in (parse_report(d) for d in docs) if r is not None]


def tls_options(uri: str) -> dict[str, Any]:
    """Verify Atlas certificates against certifi's CA bundle.

    Some Python builds (python.org on macOS) ship without a usable system trust store, so
    TLS to Atlas fails with CERTIFICATE_VERIFY_FAILED. Passing tlsCAFile also switches TLS
    on, so plain local URIs (mongodb://host without tls=true) are left alone.
    """
    lowered = uri.lower()
    uses_tls = lowered.startswith("mongodb+srv://") or any(
        flag in lowered for flag in ("tls=true", "ssl=true")
    )
    return {"tlsCAFile": certifi.where()} if uses_tls else {}


def _deadline(budget_s: float | None) -> AbstractContextManager[None]:
    """A driver-level deadline (pymongo.timeout) rather than cancelling the coroutine."""
    return pymongo.timeout(budget_s) if budget_s is not None else nullcontext()


def bbox_polygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict[str, Any]:
    ring = [[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat]]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


class ReportsRepository:
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

    def _failed(self, op: str, exc: Exception) -> None:
        # Exception text can echo the connection string; log the type only.
        log.warning("street reports %s failed: %s", op, type(exc).__name__)
        self._down_until = self._clock() + COOLDOWN_S

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

    async def ping(self) -> Status:
        if not self.configured:
            return "not_configured"
        coll = self._collection()
        if coll is None:
            return "unavailable"
        try:
            await coll.database.command("ping")
        except PyMongoError as exc:
            self._failed("ping", exc)
            return "unavailable"
        return "ok"

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

    async def indexes_ok(self) -> bool:
        coll = self._collection()
        if coll is None:
            return False
        try:
            existing = await coll.index_information()
        except PyMongoError as exc:
            self._failed("index_information", exc)
            return False
        return set(INDEX_NAMES) <= set(existing)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def report(
        self, seg_id: int, category: str, street: str, lon: float, lat: float, now: datetime
    ) -> StreetReport | None:
        """One atomic upsert: a repeat report confirms the existing one and extends its expiry."""
        coll = self._collection()
        if coll is None:
            return None
        query = {"seg_id": seg_id, "category": category}
        update = {
            "$inc": {"confirmations": 1},
            "$set": {"updated_at": now, "expires_at": now + REPORT_TTL},
            "$setOnInsert": {
                "created_at": now,
                "street": street,
                "loc": {"type": "Point", "coordinates": [lon, lat]},
            },
        }
        try:
            doc = await self._upsert(coll, query, update)
        except PyMongoError as exc:
            self._failed("report", exc)
            return None
        return parse_report(doc) if doc is not None else None

    @staticmethod
    async def _upsert(coll: Any, query: dict[str, Any], update: dict[str, Any]) -> Any:
        async def attempt() -> Any:
            return await coll.find_one_and_update(
                query,
                update,
                upsert=True,
                return_document=ReturnDocument.AFTER,
                projection=PROJECTION,
            )

        try:
            return await attempt()
        except DuplicateKeyError:
            # Two first reports raced on the unique index; the retry confirms the winner's.
            return await attempt()

    async def _find(
        self, op: str, query: dict[str, Any], limit: int, budget_s: float | None = None
    ) -> list[StreetReport] | None:
        coll = self._collection()
        if coll is None:
            return None
        cursor = coll.find(query, PROJECTION).sort("confirmations", DESCENDING).limit(limit)
        try:
            with _deadline(budget_s):
                docs = await cursor.to_list(None)
        except PyMongoError as exc:  # includes the driver's own deadline-exceeded errors
            self._failed(op, exc)
            return None
        return _parse_many(docs)

    async def for_segments(
        self,
        seg_ids: Sequence[int],
        now: datetime | None = None,
        budget_s: float | None = None,
    ) -> list[StreetReport] | None:
        """Active reports on these segments (a route), most-confirmed first.

        `budget_s` caps the wait for latency-sensitive callers; a timeout counts as a failure
        so the cooldown keeps later routes off a slow cluster.
        """
        if not self.configured:
            return None
        if not seg_ids:
            return []
        query = {"seg_id": {"$in": list(seg_ids)}, "expires_at": {"$gt": now or _utcnow()}}
        return await self._find("for_segments", query, SEGMENT_LIMIT, budget_s)

    async def in_bbox(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        now: datetime | None = None,
    ) -> list[StreetReport] | None:
        """Active reports inside the map viewport ($geoWithin on the 2dsphere index)."""
        polygon = bbox_polygon(min_lon, min_lat, max_lon, max_lat)
        query = {
            "loc": {"$geoWithin": {"$geometry": polygon}},
            "expires_at": {"$gt": now or _utcnow()},
        }
        return await self._find("in_bbox", query, BBOX_LIMIT)

    async def summary(self, now: datetime | None = None) -> list[CategoryCount] | None:
        """Active reports and confirmations per category, grouped inside Atlas."""
        coll = self._collection()
        if coll is None:
            return None
        pipeline: list[dict[str, Any]] = [
            {"$match": {"expires_at": {"$gt": now or _utcnow()}}},
            {
                "$group": {
                    "_id": "$category",
                    "reports": {"$sum": 1},
                    "confirmations": {"$sum": "$confirmations"},
                }
            },
            {"$sort": {"confirmations": -1, "reports": -1, "_id": 1}},
        ]
        try:
            cursor = await coll.aggregate(pipeline)
            rows = await cursor.to_list(None)
        except PyMongoError as exc:
            self._failed("summary", exc)
            return None
        return [
            CategoryCount(str(r["_id"]), int(r["reports"]), int(r["confirmations"]))
            for r in rows
            if r.get("_id") in CATEGORY_LABELS
        ]
