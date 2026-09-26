"""History repository degrades to None/unavailable instead of failing requests."""

from __future__ import annotations

import pytest
from app.repositories.history import HistoryRepository


@pytest.mark.unit
async def test_unconfigured_repository_is_inert() -> None:
    repo = HistoryRepository(None)

    assert not repo.configured
    assert await repo.ping() == "not_configured"
    assert await repo.hourly(3) is None


@pytest.mark.unit
async def test_unreachable_database_reports_unavailable() -> None:
    repo = HistoryRepository("postgresql://nobody:x@127.0.0.1:1/none")

    assert await repo.ping() == "unavailable"
    assert await repo.hourly(3) is None
