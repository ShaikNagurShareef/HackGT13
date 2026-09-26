"""Ride network: bike-infrastructure classes from OSM tags and the City facilities layer."""

from __future__ import annotations

import pytest
from pathpulse_data.network.bike import BikeInfra, city_infra, is_beltline, osm_infra


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"highway": "cycleway"}, BikeInfra.PROTECTED),
        ({"highway": "path", "bicycle": "designated"}, BikeInfra.PROTECTED),
        ({"highway": "path", "bicycle": "yes"}, BikeInfra.NONE),
        ({"highway": "secondary", "cycleway:right": "track"}, BikeInfra.PROTECTED),
        ({"highway": "secondary", "cycleway": "separate"}, BikeInfra.PROTECTED),
        ({"highway": "tertiary", "cycleway:both": "lane"}, BikeInfra.PAINTED),
        ({"highway": "residential", "cycleway": "shared_lane"}, BikeInfra.SHARED),
        ({"highway": "primary", "cycleway": "no"}, BikeInfra.NONE),
        ({"highway": "primary"}, BikeInfra.NONE),
        ({"highway": "primary", "cycleway": float("nan")}, BikeInfra.NONE),
    ],
)
def test_osm_infra_classes(tags: dict[str, object], expected: BikeInfra) -> None:
    assert osm_infra(tags) == expected


@pytest.mark.unit
def test_osm_infra_takes_the_strongest_side_and_joined_list_values() -> None:
    tags = {
        "highway": "secondary;tertiary",
        "cycleway:left": "shared_lane",
        "cycleway:right": "lane",
    }

    assert osm_infra(tags) == BikeInfra.PAINTED
    assert osm_infra({"highway": "residential;cycleway"}) == BikeInfra.PROTECTED


@pytest.mark.unit
@pytest.mark.parametrize(
    ("simple", "status", "expected"),
    [
        ("Protected Bike Lane", "Existing", BikeInfra.PROTECTED),
        ("Shared-Use Path", "Existing", BikeInfra.PROTECTED),
        ("Painted Bike Lane", "Existing", BikeInfra.PAINTED),
        ("Bike-Friendly Street", "Existing", BikeInfra.SHARED),
        ("Protected Bike Lane", "Planned", BikeInfra.NONE),
        ("Protected Bike Lane", "Funded", BikeInfra.NONE),
        (None, "Existing", BikeInfra.NONE),
    ],
)
def test_city_infra_counts_only_existing_facilities(
    simple: str | None, status: str, expected: BikeInfra
) -> None:
    assert city_infra(simple, status) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Atlanta BeltLine Eastside Trail", True),
        ("Westside Trail", True),
        ("Beltline Connector;Irwin Street", True),
        ("Freedom Park Trail", False),
        (None, False),
    ],
)
def test_is_beltline_by_name(name: str | None, expected: bool) -> None:
    assert is_beltline(name) is expected
