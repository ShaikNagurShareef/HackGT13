"""Shared-walk repository: insert, expiry-aware reads, conditional updates, graceful failure."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from app.domain.walks import WALK_TTL, Destination, SharedWalk, WalkPosition
from app.repositories.walks import (
    COLLECTION,
    INDEX_NAMES,
    WalksRepository,
    WalksUnavailableError,
    parse_walk,
    walk_doc,
)
from pymongo.errors import ServerSelectionTimeoutError

from tests.fake_mongo import FakeCollection

NOW = datetime(2026, 9, 26, 22, 30, tzinfo=UTC)
DEST = Destination(label="Midtown MARTA", lat=33.781, lon=-84.3863)


def _walk(walk_id: str = "w" * 22, **changes: object) -> SharedWalk:
    base = SharedWalk(
        walk_id=walk_id,
        token_hash="a" * 64,
        status="walking",
        destination=DEST,
        eta_at=NOW + timedelta(minutes=12),
        position=None,
        route=((-84.3962, 33.7771), (-84.3863, 33.781)),
        created_at=NOW,
        updated_at=NOW,
        expires_at=NOW + WALK_TTL,
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def _repo() -> tuple[WalksRepository, FakeCollection]:
    fake = FakeCollection()
    return WalksRepository(None, collection=fake), fake


@pytest.mark.unit
async def test_unconfigured_repository_raises_unavailable() -> None:
    repo = WalksRepository(None)

    assert not repo.configured
    assert await repo.ensure_indexes() is False
    with pytest.raises(WalksUnavailableError):
        await repo.create(_walk())
    with pytest.raises(WalksUnavailableError):
        await repo.get("x" * 22, NOW)
    with pytest.raises(WalksUnavailableError):
        await repo.save_update(_walk(), _walk())
    await repo.close()


@pytest.mark.unit
async def test_ensure_indexes_creates_ttl_and_walk_id_indexes() -> None:
    repo, fake = _repo()

    assert await repo.ensure_indexes() is True

    assert COLLECTION == "shared_walks"
    assert set(INDEX_NAMES) == set(fake.indexes)
    ttl = fake.indexes["expires_at_ttl"]
    assert ttl["expireAfterSeconds"] == 0
    assert dict(ttl["key"]) == {"expires_at": 1}
    walk_id = fake.indexes["walk_id_unique"]
    assert dict(walk_id["key"]) == {"walk_id": 1} and walk_id["unique"] is True


@pytest.mark.unit
async def test_create_then_get_round_trips_without_mongo_id() -> None:
    repo, fake = _repo()
    walk = _walk(position=WalkPosition(lat=33.777, lon=-84.39, accuracy_m=8.0, at=NOW))

    await repo.create(walk)
    found = await repo.get(walk.walk_id, NOW + timedelta(seconds=5))

    assert found == walk
    assert fake.docs[0]["token_hash"] == "a" * 64
    assert fake.calls[-1] == (
        "find_one",
        {"walk_id": walk.walk_id, "expires_at": {"$gt": NOW + timedelta(seconds=5)}},
    )


@pytest.mark.unit
async def test_get_ignores_expired_and_missing_walks() -> None:
    repo, _ = _repo()
    await repo.create(_walk())

    assert await repo.get("w" * 22, NOW + WALK_TTL + timedelta(seconds=1)) is None
    assert await repo.get("z" * 22, NOW) is None


@pytest.mark.unit
async def test_save_update_is_conditional_on_the_previous_update_time() -> None:
    repo, fake = _repo()
    walk = _walk()
    await repo.create(walk)
    later = NOW + timedelta(seconds=5)
    moved = _walk(
        position=WalkPosition(lat=33.778, lon=-84.391, accuracy_m=None, at=later),
        updated_at=later,
        expires_at=later + WALK_TTL,
        status="arrived",
    )

    saved = await repo.save_update(walk, moved)
    stale = await repo.save_update(walk, moved)  # lost the race: updated_at no longer matches

    assert saved == moved
    assert stale is None
    query, update, upsert = fake.calls[-1][1]
    assert query == {"walk_id": walk.walk_id, "updated_at": NOW}
    assert upsert is False
    assert set(update["$set"]) == {"status", "eta_at", "position", "updated_at", "expires_at"}


@pytest.mark.unit
async def test_atlas_failure_raises_and_cools_down() -> None:
    clock = [100.0]
    fake = FakeCollection()
    repo = WalksRepository(None, collection=fake, clock=lambda: clock[0])
    fake.fail = ServerSelectionTimeoutError("down")

    with pytest.raises(WalksUnavailableError):
        await repo.get("w" * 22, NOW)
    fake.fail = None
    calls = len(fake.calls)
    with pytest.raises(WalksUnavailableError):  # still cooling down: no network call
        await repo.create(_walk())
    assert len(fake.calls) == calls
    assert await repo.ensure_indexes() is False

    clock[0] += 31
    await repo.create(_walk())
    assert len(fake.docs) == 1


@pytest.mark.unit
async def test_ensure_indexes_failure_is_reported() -> None:
    repo, fake = _repo()
    fake.fail = ServerSelectionTimeoutError("down")

    assert await repo.ensure_indexes() is False


@pytest.mark.unit
async def test_save_update_failure_raises_unavailable() -> None:
    repo, fake = _repo()
    await repo.create(_walk())
    fake.fail = ServerSelectionTimeoutError("down")

    with pytest.raises(WalksUnavailableError):
        await repo.save_update(_walk(), _walk(status="ended"))


@pytest.mark.unit
async def test_invalid_uri_is_unavailable_not_a_crash() -> None:
    repo = WalksRepository("not-a-mongo-uri")

    assert repo.configured
    with pytest.raises(WalksUnavailableError):
        await repo.get("w" * 22, NOW)


@pytest.mark.unit
async def test_real_client_is_built_lazily_and_closed() -> None:
    repo = WalksRepository("mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=50", "pathpulse_test")

    coll = repo._collection()  # no I/O: the driver connects on first operation

    assert coll is not None and coll.name == COLLECTION
    await repo.close()
    await repo.close()


@pytest.mark.unit
def test_walk_doc_round_trips_and_malformed_docs_are_skipped() -> None:
    walk = _walk(position=WalkPosition(lat=33.777, lon=-84.39, accuracy_m=None, at=NOW))
    doc = walk_doc(walk)

    assert parse_walk(doc) == walk
    assert doc["route"] == [[-84.3962, 33.7771], [-84.3863, 33.781]]
    assert parse_walk({**doc, "status": "teleported"}) is None
    assert parse_walk({**doc, "created_at": "yesterday"}) is None
    assert parse_walk({k: v for k, v in doc.items() if k != "destination"}) is None
    assert parse_walk({**doc, "route": None}) == dataclasses.replace(walk, route=None)
