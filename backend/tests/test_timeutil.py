"""Atlanta-local time handling: departure parsing, day groups, light, DST (EC-22, EC-25)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.domain.timeutil import (
    ATLANTA,
    Cell,
    cell_at,
    day_group,
    light_at,
    parse_departure,
)

NOW = datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA)


@pytest.mark.unit
def test_parse_now_and_relative() -> None:
    assert parse_departure("now", now=NOW) == NOW
    assert parse_departure("+15m", now=NOW) == NOW + timedelta(minutes=15)
    assert parse_departure("+1h", now=NOW) == NOW + timedelta(hours=1)


@pytest.mark.unit
def test_parse_iso_converts_to_atlanta() -> None:
    utc = datetime(2026, 9, 26, 2, 30, tzinfo=UTC)

    parsed = parse_departure(utc.isoformat(), now=NOW)

    assert parsed.tzinfo == ATLANTA
    assert parsed.hour == 22


@pytest.mark.unit
def test_naive_iso_is_interpreted_as_atlanta_time() -> None:
    parsed = parse_departure("2026-09-26T01:00", now=NOW)

    assert parsed.hour == 1
    assert parsed.utcoffset() == timedelta(hours=-4)


@pytest.mark.unit
def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="departure"):
        parse_departure("tomorrow-ish", now=NOW)


@pytest.mark.unit
def test_day_groups_and_light() -> None:
    assert day_group(NOW) == "friday"
    assert light_at(NOW) == "dark"
    assert light_at(NOW.replace(hour=13)) == "day"


@pytest.mark.unit
def test_seven_pm_september_is_dusk_or_dark() -> None:
    # PRD COND-03: 7 PM in late September renders as dusk/dark (sunset ~7:32 PM).
    assert light_at(datetime(2026, 9, 25, 19, 50, tzinfo=ATLANTA)) in {"twilight", "dark"}


@pytest.mark.unit
def test_dst_repeated_hour_maps_to_same_bucket() -> None:
    first = datetime(2026, 11, 1, 1, 30, tzinfo=ATLANTA, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=ATLANTA, fold=1)

    assert cell_at(first, wet=False).hour == cell_at(second, wet=False).hour == 1


@pytest.mark.unit
def test_cell_at_bundles_all_keys() -> None:
    cell = cell_at(NOW, wet=True)

    assert cell == Cell(day_group="friday", hour=22, light="dark", wet=True)
    assert cell.key == ("friday", 22, "dark", True)


@pytest.mark.unit
@pytest.mark.parametrize("value", ["0001-01-01T00:00+14:00", "2099-01-01T00:00"])
def test_parse_rejects_extreme_departures(value: str) -> None:
    with pytest.raises(ValueError, match="departure"):
        parse_departure(value, now=NOW)
