"""Share-my-walk service edges: clock precision, token hashing, and outages mid-request."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.api.envelope import AppError
from app.api.walk_schemas import CreateWalkRequest, PositionUpdateRequest
from app.api.walks import get_clock
from app.repositories.walks import WalksRepository, parse_walk, walk_doc
from app.services.walks import (
    create_walk,
    get_walk,
    hash_token,
    token_matches,
    update_position,
    utcnow,
)
from pymongo.errors import ServerSelectionTimeoutError

from tests.fake_mongo import FakeCollection

T0 = datetime(2026, 9, 26, 22, 30, tzinfo=UTC)
CREATE = CreateWalkRequest.model_validate(
    {"destination": {"label": "Midtown MARTA", "lat": 33.781, "lon": -84.3863}, "eta_s": 600}
)


async def _created() -> tuple[WalksRepository, FakeCollection, str, str]:
    fake = FakeCollection()
    repo = WalksRepository(None, collection=fake)
    created = await create_walk(repo, CREATE, T0)
    return repo, fake, created.walk_id, created.owner_token


@pytest.mark.unit
def test_clock_is_utc_with_millisecond_precision_like_mongodb() -> None:
    now = get_clock()()

    assert now.tzinfo is UTC
    assert now.microsecond % 1000 == 0
    assert abs(utcnow() - now) < timedelta(seconds=5)


@pytest.mark.unit
def test_tokens_are_compared_by_hash() -> None:
    digest = hash_token("owner-token-value")

    assert len(digest) == 64
    assert token_matches("owner-token-value", digest)
    assert not token_matches("owner-token-valuf", digest)


@pytest.mark.unit
async def test_follow_during_an_outage_is_a_503() -> None:
    repo, fake, walk_id, _ = await _created()
    fake.fail = ServerSelectionTimeoutError("down")

    with pytest.raises(AppError) as err:
        await get_walk(repo, walk_id, T0)

    assert err.value.status == 503 and err.value.code == "WALKS_UNAVAILABLE"


@pytest.mark.unit
async def test_position_save_during_an_outage_is_a_503() -> None:
    repo, fake, walk_id, token = await _created()
    req = PositionUpdateRequest(owner_token=token, lat=33.777, lon=-84.39)
    original_find_one = fake.find_one

    async def find_then_fail(*args: object, **kwargs: object) -> object:
        doc = await original_find_one(*args, **kwargs)  # type: ignore[arg-type]
        fake.fail_once = ServerSelectionTimeoutError("down")
        return doc

    fake.find_one = find_then_fail  # type: ignore[method-assign]

    with pytest.raises(AppError) as err:
        await update_position(repo, walk_id, req, T0 + timedelta(seconds=5))

    assert err.value.status == 503


@pytest.mark.unit
def test_route_that_is_not_a_list_is_malformed() -> None:
    doc = {**walk_doc_for_test(), "route": "not a route"}

    assert parse_walk(doc) is None


def walk_doc_for_test() -> dict[str, object]:
    walk = parse_walk(
        {
            "walk_id": "w" * 22,
            "token_hash": "a" * 64,
            "status": "walking",
            "destination": {"label": "Home", "lat": 33.78, "lon": -84.39},
            "eta_at": T0,
            "position": None,
            "route": None,
            "created_at": T0,
            "updated_at": T0,
            "expires_at": T0,
        }
    )
    assert walk is not None
    return walk_doc(walk)
