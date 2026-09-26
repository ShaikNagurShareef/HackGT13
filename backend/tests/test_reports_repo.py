"""Community street reports repository: atomic upserts, geo queries, TTL, graceful fallback."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from app.domain.reports import CATEGORY_LABELS, REPORT_TTL
from app.repositories.reports import (
    BBOX_LIMIT,
    INDEX_NAMES,
    ReportsRepository,
)
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from tests.fake_mongo import FakeCollection

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
LON, LAT = -84.39, 33.776


def _repo(coll: FakeCollection | None = None) -> tuple[ReportsRepository, FakeCollection]:
    fake = coll or FakeCollection()
    return ReportsRepository(None, collection=fake), fake


@pytest.mark.unit
async def test_unconfigured_repository_is_inert() -> None:
    repo = ReportsRepository(None)

    assert not repo.configured
    assert await repo.ping() == "not_configured"
    assert await repo.ensure_indexes() is False
    assert await repo.indexes_ok() is False
    assert await repo.report(1, "signal_out", "A St", LON, LAT, NOW) is None
    assert await repo.for_segments([1]) is None
    assert await repo.in_bbox(-84.4, 33.7, -84.3, 33.8) is None
    assert await repo.summary() is None
    await repo.close()


@pytest.mark.unit
async def test_first_report_inserts_with_fourteen_day_expiry() -> None:
    repo, fake = _repo()

    report = await repo.report(7, "construction", "Spring St", LON, LAT, NOW)

    assert report is not None
    assert report.confirmations == 1
    assert report.created_at == NOW
    assert report.expires_at == NOW + timedelta(days=14) == NOW + REPORT_TTL
    assert (report.lon, report.lat, report.street) == (LON, LAT, "Spring St")
    query, update, upsert = fake.calls[0][1]
    assert fake.calls[0][0] == "find_one_and_update" and upsert is True
    assert query == {"seg_id": 7, "category": "construction"}
    assert update["$inc"] == {"confirmations": 1}
    assert update["$setOnInsert"]["loc"] == {"type": "Point", "coordinates": [LON, LAT]}
    assert "created_at" not in update["$set"]


@pytest.mark.unit
async def test_repeat_report_confirms_and_extends_expiry() -> None:
    repo, fake = _repo()
    later = NOW + timedelta(days=3)

    await repo.report(7, "construction", "Spring St", LON, LAT, NOW)
    again = await repo.report(7, "construction", "Spring St", LON + 1, LAT, later)

    assert again is not None
    assert again.confirmations == 2
    assert again.created_at == NOW
    assert again.updated_at == later
    assert again.expires_at == later + REPORT_TTL
    assert again.lon == LON  # location is fixed on insert
    assert len(fake.docs) == 1


@pytest.mark.unit
async def test_concurrent_insert_race_retries_once() -> None:
    repo, fake = _repo()
    fake.fail_once = DuplicateKeyError("E11000")

    report = await repo.report(7, "signal_out", "Spring St", LON, LAT, NOW)

    assert report is not None and report.confirmations == 1
    assert [c[0] for c in fake.calls] == ["find_one_and_update", "find_one_and_update"]


@pytest.mark.unit
async def test_bbox_query_uses_closed_geojson_polygon_and_limit() -> None:
    repo, fake = _repo()
    await repo.report(1, "flooding", "In St", -84.39, 33.77, NOW)
    await repo.report(2, "flooding", "Out St", -84.10, 33.77, NOW)

    found = await repo.in_bbox(-84.40, 33.76, -84.38, 33.78, now=NOW)

    assert found is not None and [r.street for r in found] == ["In St"]
    query = fake.calls[-1][1]
    ring = query["loc"]["$geoWithin"]["$geometry"]["coordinates"][0]
    assert query["loc"]["$geoWithin"]["$geometry"]["type"] == "Polygon"
    assert ring[0] == ring[-1] == [-84.40, 33.76]
    assert len(ring) == 5
    assert query["expires_at"] == {"$gt": NOW}
    assert fake.cursors[-1].limit_n == BBOX_LIMIT == 300


@pytest.mark.unit
async def test_for_segments_filters_ids_and_skips_expired() -> None:
    repo, fake = _repo()
    await repo.report(1, "poor_lighting", "A St", LON, LAT, NOW - timedelta(days=20))
    await repo.report(2, "poor_lighting", "B St", LON, LAT, NOW)
    await repo.report(3, "poor_lighting", "C St", LON, LAT, NOW)

    found = await repo.for_segments([1, 2], now=NOW)

    assert found is not None and [r.seg_id for r in found] == [2]
    assert fake.calls[-1][1]["seg_id"] == {"$in": [1, 2]}
    assert await repo.for_segments([]) == []


@pytest.mark.unit
async def test_summary_groups_by_category_in_the_database() -> None:
    repo, fake = _repo()
    await repo.report(1, "signal_out", "A St", LON, LAT, NOW)
    await repo.report(1, "signal_out", "A St", LON, LAT, NOW)
    await repo.report(2, "signal_out", "B St", LON, LAT, NOW)
    await repo.report(3, "construction", "C St", LON, LAT, NOW)

    rows = await repo.summary(now=NOW)

    assert rows is not None
    assert [(r.category, r.reports, r.confirmations) for r in rows] == [
        ("signal_out", 2, 3),
        ("construction", 1, 1),
    ]
    pipeline = fake.calls[-1][1]
    assert [next(iter(stage)) for stage in pipeline] == ["$match", "$group", "$sort"]
    assert pipeline[1]["$group"]["_id"] == "$category"


@pytest.mark.unit
async def test_ensure_indexes_creates_geo_ttl_and_unique_indexes() -> None:
    repo, fake = _repo()

    assert await repo.indexes_ok() is False
    assert await repo.ensure_indexes() is True
    assert await repo.indexes_ok() is True

    specs = fake.indexes
    assert set(specs) == set(INDEX_NAMES)
    by_key = {tuple(spec["key"].items()): spec for spec in specs.values()}
    assert (("loc", "2dsphere"),) in by_key
    assert by_key[(("expires_at", 1),)]["expireAfterSeconds"] == 0
    assert by_key[(("seg_id", 1), ("category", 1))]["unique"] is True


@pytest.mark.unit
async def test_database_errors_degrade_and_log_type_only(caplog: pytest.LogCaptureFixture) -> None:
    repo, fake = _repo()
    fake.fail = ServerSelectionTimeoutError("mongodb+srv://user:hunter2@cluster")

    with caplog.at_level(logging.WARNING):
        assert await repo.report(1, "signal_out", "A St", LON, LAT, NOW) is None
    assert await repo.ping() == "unavailable"
    assert await repo.in_bbox(-84.4, 33.7, -84.3, 33.8) is None
    assert await repo.for_segments([1]) is None
    assert await repo.summary() is None
    assert await repo.ensure_indexes() is False
    assert "ServerSelectionTimeoutError" in caplog.text
    assert "hunter2" not in caplog.text


@pytest.mark.unit
async def test_cooldown_skips_the_database_after_a_failure() -> None:
    clock = [100.0]
    fake = FakeCollection()
    repo = ReportsRepository(None, collection=fake, clock=lambda: clock[0])
    fake.fail = ServerSelectionTimeoutError("down")

    assert await repo.for_segments([1]) is None
    calls = len(fake.calls)
    assert await repo.for_segments([1]) is None
    assert len(fake.calls) == calls  # no round trip while cooling down

    fake.fail = None
    clock[0] += 60
    assert await repo.for_segments([1]) == []


@pytest.mark.unit
async def test_malformed_documents_are_skipped() -> None:
    repo, fake = _repo()
    await repo.report(1, "signal_out", "A St", LON, LAT, NOW)
    fake.docs.append({"_id": 99, "seg_id": 2, "category": "signal_out", "expires_at": NOW})

    found = await repo.for_segments([1, 2], now=NOW - timedelta(days=1))

    assert found is not None and [r.seg_id for r in found] == [1]


@pytest.mark.unit
async def test_unreachable_or_invalid_uri_reports_unavailable() -> None:
    bad = ReportsRepository("not-a-mongo-uri")
    down = ReportsRepository("mongodb://127.0.0.1:1/")

    assert bad.configured and await bad.ping() == "unavailable"
    assert await down.ping() == "unavailable"
    await down.close()


@pytest.mark.unit
def test_every_category_has_a_plain_label() -> None:
    banned = ("safe", "dangerous", "crime", "guaranteed")

    assert len(CATEGORY_LABELS) == 6
    for label in CATEGORY_LABELS.values():
        assert label and not any(word in label.lower() for word in banned)
