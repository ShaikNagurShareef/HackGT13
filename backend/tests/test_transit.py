"""MARTA rail hand-off: the committed station list and GET /transit/stations."""

from __future__ import annotations

import pytest
from app.domain.transit import load_rail_stations, stations_in_bbox

REAL_CITY_BBOX = [-84.55085, 33.64792, -84.28956, 33.88682]


@pytest.mark.unit
def test_static_list_has_all_38_marta_rail_stations() -> None:
    stations = load_rail_stations()

    assert len(stations) == 38
    assert len({s.name for s in stations}) == 38
    assert all(33.6 < s.lat < 34.0 and -84.5 < s.lon < -84.2 for s in stations)
    five_points = next(s for s in stations if s.name == "Five Points")
    assert set(five_points.lines) == {"Red", "Gold", "Blue", "Green"}


@pytest.mark.unit
def test_bbox_keeps_city_stations_and_drops_suburban_ones() -> None:
    names = {s.name for s in stations_in_bbox(load_rail_stations(), REAL_CITY_BBOX)}

    assert {"Five Points", "Inman Park/Reynoldstown", "Midtown", "Lindbergh Center"} <= names
    assert not names & {"North Springs", "Doraville", "Indian Creek", "Airport"}
    assert len(names) == 28
