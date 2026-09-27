"""Housekeeping: delete stale Ask PathPro memory clones. All Backboard HTTP is mocked."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from app.config import Settings
from app.services.backboard import BACKBOARD_API, Backboard
from app.tools.prune_backboard import main_async, parse_age, prune

KEY = "bb-prune-key-do-not-print"
BASE = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
OLD = "aaaaaaaa-0000-4000-8000-000000000001"
OLD_Z = "aaaaaaaa-0000-4000-8000-000000000002"
FRESH = "aaaaaaaa-0000-4000-8000-000000000003"
NO_DATE = "aaaaaaaa-0000-4000-8000-000000000004"
OTHER = "aaaaaaaa-0000-4000-8000-000000000005"


def _assistant(assistant_id: str, name: str, created_at: str | None) -> dict[str, str]:
    row = {"assistant_id": assistant_id, "name": name}
    return {**row, "created_at": created_at} if created_at else row


LISTING = [
    _assistant(BASE, "PathPro docs assistant", "2025-01-01T00:00:00"),
    _assistant(OLD, "pathpro-visitor-0a1b2c3d4e5f", "2026-07-01T00:00:00"),
    _assistant(OLD_Z, "pathpro-visitor-ffffffffffff", "2026-08-01T10:00:00Z"),
    _assistant(FRESH, "pathpro-visitor-000000000000", "2026-09-20T00:00:00"),
    _assistant(NO_DATE, "pathpro-visitor-111111111111", None),
    _assistant(OTHER, "someone-else", "2020-01-01T00:00:00"),
]


def _mock(mock: respx.MockRouter, status: int = 200) -> respx.Route:
    mock.get(f"{BACKBOARD_API}/assistants").mock(return_value=httpx.Response(200, json=LISTING))
    return mock.delete(url__regex=rf"{BACKBOARD_API}/assistants/[\w-]+$").mock(
        return_value=httpx.Response(status, json={})
    )


def _deleted(route: respx.Route) -> set[str]:
    return {call.request.url.path.rsplit("/", 1)[-1] for call in route.calls}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "age"),
    [("30d", timedelta(days=30)), ("12h", timedelta(hours=12)), ("1d", timedelta(days=1))],
)
def test_parse_age(raw: str, age: timedelta) -> None:
    assert parse_age(raw) == age


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["", "30", "d", "-1d", "0d", "3w", "30 days"])
def test_parse_age_rejects_bad_values(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_age(raw)


@pytest.mark.unit
async def test_prune_deletes_only_old_visitor_clones() -> None:
    with respx.mock() as mock:
        delete = _mock(mock)
        async with httpx.AsyncClient() as client:
            result = await prune(Backboard(client, KEY), timedelta(days=30), now=NOW)

    assert _deleted(delete) == {OLD, OLD_Z}
    assert (result.matched, result.deleted, result.failed) == (2, 2, 0)
    for call in delete.calls:
        assert call.request.headers["X-API-Key"] == KEY


@pytest.mark.unit
async def test_prune_dry_run_deletes_nothing() -> None:
    with respx.mock() as mock:
        delete = _mock(mock)
        async with httpx.AsyncClient() as client:
            result = await prune(Backboard(client, KEY), timedelta(days=30), now=NOW, dry_run=True)

    assert not delete.called
    assert (result.matched, result.deleted, result.failed) == (2, 0, 0)


@pytest.mark.unit
async def test_prune_counts_failed_deletes_and_carries_on() -> None:
    with respx.mock() as mock:
        delete = _mock(mock, status=500)
        async with httpx.AsyncClient() as client:
            result = await prune(Backboard(client, KEY), timedelta(days=30), now=NOW)

    assert delete.call_count == 2
    assert (result.matched, result.deleted, result.failed) == (2, 0, 2)


@pytest.mark.unit
async def test_prune_accepts_a_wrapped_listing() -> None:
    with respx.mock() as mock:
        mock.get(f"{BACKBOARD_API}/assistants").mock(
            return_value=httpx.Response(200, json={"assistants": LISTING})
        )
        delete = mock.delete(url__regex=rf"{BACKBOARD_API}/assistants/[\w-]+$").mock(
            return_value=httpx.Response(200, json={})
        )
        async with httpx.AsyncClient() as client:
            await prune(Backboard(client, KEY), timedelta(days=30), now=NOW)

    assert _deleted(delete) == {OLD, OLD_Z}


@pytest.mark.unit
async def test_main_prints_counts_only(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = Settings(backboard_api_key=KEY, backboard_assistant_id=BASE, _env_file=None)  # type: ignore[call-arg]
    with respx.mock() as mock:
        _mock(mock)
        code = await main_async(cfg, ["--older-than", "30d", "--dry-run"])

    out = capsys.readouterr().out
    assert code == 0
    assert "2" in out
    for secret_or_id in (KEY, OLD, OLD_Z, BASE, "pathpro-visitor-0a1b"):
        assert secret_or_id not in out


@pytest.mark.unit
async def test_main_without_key_makes_no_calls(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(host="app.backboard.io")
        code = await main_async(cfg, [])

    assert code == 2
    assert not route.called
    assert "BACKBOARD_API_KEY" in capsys.readouterr().out


@pytest.mark.unit
async def test_main_rejects_a_bad_age(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = Settings(backboard_api_key=KEY, _env_file=None)  # type: ignore[call-arg]
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(host="app.backboard.io")
        code = await main_async(cfg, ["--older-than", "soon"])

    assert code == 1
    assert not route.called


@pytest.mark.unit
async def test_main_upstream_failure_prints_type_name_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = Settings(backboard_api_key=KEY, _env_file=None)  # type: ignore[call-arg]
    with respx.mock() as mock:
        mock.get(f"{BACKBOARD_API}/assistants").mock(return_value=httpx.Response(401))
        code = await main_async(cfg, [])

    out = capsys.readouterr().out
    assert code == 1
    assert "HTTPStatusError" in out and KEY not in out
