"""The key checker reports MongoDB Atlas status without printing the URI."""

from __future__ import annotations

import pytest
from app.repositories.reports import ReportsRepository
from app.tools.check_keys import FAIL, MISSING, OK, check_mongo
from pymongo.errors import ServerSelectionTimeoutError

from tests.fake_mongo import FakeCollection


@pytest.mark.unit
async def test_mongo_missing_uri() -> None:
    status, note = await check_mongo(ReportsRepository(None))

    assert status == MISSING and "MONGODB_URI" in note


@pytest.mark.unit
async def test_mongo_ping_and_indexes() -> None:
    fake = FakeCollection()
    repo = ReportsRepository(None, collection=fake)

    before = await check_mongo(repo)
    await repo.ensure_indexes()
    after = await check_mongo(repo)

    assert before[0] == FAIL and "MISSING" in before[1]
    assert after == (OK, "ping ok, indexes OK")


@pytest.mark.unit
async def test_mongo_unreachable() -> None:
    fake = FakeCollection()
    fake.fail = ServerSelectionTimeoutError("mongodb+srv://u:secret@x")

    status, note = await check_mongo(ReportsRepository(None, collection=fake))

    assert status == FAIL and "secret" not in note
