"""Evidence resolution shared by /explain and Ask PathPro, plus area and conditions evidence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx
from app.api.envelope import AppError
from app.api.schemas import ConditionUsed, FactorOut, NamedSegmentOut, RouteOut, RoutesData
from app.domain.timeutil import ATLANTA, cell_at
from app.repositories.artifacts import Bundle, load_bundle
from app.repositories.hexes import load_hexes
from app.services.areas import AreaDetail, resolve_area_detail
from app.services.explain.evidence import area_evidence, conditions_evidence
from app.services.explain.resolve import (
    resolve_area_evidence,
    resolve_conditions_evidence,
    resolve_route_evidence,
    resolve_segment_evidence,
)
from app.services.weather import FORECAST_URL, Resolved, WeatherService

from tests.bundle_factory import write_bundle, write_hexes

VERSION = "pp-test-0001"
ROUTE_KEY = "ab" * 8
NIGHT = "2026-09-25T22:30"
NOON = "2026-09-25T12:00"
DRY = ConditionUsed(cond="dry", source="override", label="Dry (your choice)")


def _route(name: str, score: int, minutes: float) -> RouteOut:
    return RouteOut(
        coords=[[-84.39, 33.77], [-84.38, 33.78]],
        duration_s=minutes * 60,
        distance_m=1000.0,
        risk_score=score,
        band="High",
        exposure=1.0,
        high_risk_m=100.0,
        limited_data_m=0.0,
        segment_ids=[1, 2],
        top_segments=[NamedSegmentOut(seg_id=1, name=name, score=score)],
    )


def _routes() -> RoutesData:
    return RoutesData(
        condition_used=DRY,
        depart_at="2026-09-25T22:30:00-04:00",
        fastest=_route("10th Street Northwest", 90, 18),
        pathpro=_route("Juniper Street", 70, 22),
        message_code="OK",
        message=None,
        time_cost_min=4.0,
        exposure_reduction_pct=40,
        unavoidable=[],
        route_key=ROUTE_KEY,
    )


def _area(**over: object) -> AreaDetail:
    fields: dict[str, object] = {
        "cell": "8944c1a8c2bffff",
        "lat": 33.7761234,
        "lon": -84.3961234,
        "score": 72,
        "band": "High",
        "confidence": "high",
        "baseline_points": 50,
        "factors": [
            FactorOut(key="vehicle_crashes", label="Vehicle crashes nearby", points=15),
            FactorOut(key="time_conditions", label="Time of day and conditions", points=9),
            FactorOut(key="history", label="Crash history", points=-2),
        ],
        "remainder_points": 0,
        "crashes": 40.4,
        "ped_crashes": 3.2,
        "period": "2020-2024",
        "in_street_coverage": True,
        "condition_used": DRY,
        "at": datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA).isoformat(),
    }
    fields.update(over)
    return AreaDetail(**fields)  # type: ignore[arg-type]


@pytest.fixture
async def weather() -> AsyncIterator[WeatherService]:
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
            yield WeatherService(client)


# --- route -----------------------------------------------------------------------------------


@pytest.mark.unit
def test_route_evidence_resolves_from_the_cache_with_the_explain_key() -> None:
    cache = {ROUTE_KEY: _routes()}

    resolved = resolve_route_evidence(cache, ROUTE_KEY, VERSION)

    assert resolved.cache_key == f"route:{ROUTE_KEY}:{VERSION}"
    assert resolved.evidence.kind == "route"
    assert resolved.evidence.payload["pathpro"]["extra_minutes"] == 4.0


@pytest.mark.unit
@pytest.mark.parametrize("key", [None, "", "cd" * 8])
def test_missing_route_is_route_expired(key: str | None) -> None:
    with pytest.raises(AppError) as err:
        resolve_route_evidence({ROUTE_KEY: _routes()}, key, VERSION)

    assert err.value.code == "ROUTE_EXPIRED" and err.value.status == 404


# --- segment ---------------------------------------------------------------------------------


@pytest.mark.unit
async def test_segment_evidence_uses_the_explain_cache_key(
    bundle: Bundle, weather: WeatherService
) -> None:
    resolved = await resolve_segment_evidence(
        bundle, weather, seg_id=2, t=NIGHT, cond="dry", mode="walk", model_version=VERSION
    )

    at = datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA)
    cell = "|".join(map(str, cell_at(at, False).key))
    assert resolved.cache_key == f"seg:2:{cell}:{VERSION}"
    assert resolved.evidence.kind == "segment"
    assert resolved.evidence.payload["street"] == "Row 1 St"
    assert resolved.evidence.payload["time"] == "10 PM"


@pytest.mark.unit
async def test_ride_segment_keys_carry_the_mode(bundle: Bundle, weather: WeatherService) -> None:
    resolved = await resolve_segment_evidence(
        bundle, weather, seg_id=2, t=NIGHT, cond="wet", mode="bike", model_version=VERSION
    )

    assert resolved.cache_key.endswith(f":{VERSION}:bike")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("seg_id", "t", "code"),
    [(2, "not a time", "BAD_TIME"), (10_000, NIGHT, "NOT_FOUND")],
)
async def test_segment_resolution_errors(
    bundle: Bundle, weather: WeatherService, seg_id: int, t: str, code: str
) -> None:
    with pytest.raises(AppError) as err:
        await resolve_segment_evidence(
            bundle, weather, seg_id=seg_id, t=t, cond="dry", mode="walk", model_version=VERSION
        )

    assert err.value.code == code


# --- area ------------------------------------------------------------------------------------


@pytest.mark.unit
def test_area_evidence_carries_score_factors_and_history_but_no_location() -> None:
    evidence = area_evidence(_area())

    payload = evidence.payload
    assert evidence.kind == "area"
    assert payload["score"] == 72 and payload["band"] == "High"
    assert payload["time"] == "10 PM" and payload["conditions"] == "dry"
    assert payload["confidence"] == "high"
    assert payload["raises_risk"] == [
        {"factor": "Vehicle crashes nearby", "points": 15},
        {"factor": "Time of day and conditions", "points": 9},
    ]
    assert payload["lowers_risk"] == [{"factor": "Crash history", "points": 2}]
    assert payload["history"] == {"crashes": 40, "pedestrian_crashes": 3, "period": "2020-2024"}
    assert not {"lat", "lon", "cell"} & set(payload)
    assert 33.8 not in evidence.numbers and -84.4 not in evidence.numbers
    assert {72.0, 15.0, 9.0, 2.0, 40.0, 3.0} <= evidence.numbers


@pytest.mark.unit
def test_area_evidence_caps_factors() -> None:
    many = [FactorOut(key=f"k{i}", label=f"Factor {i}", points=10 - i) for i in range(6)]

    payload = area_evidence(_area(factors=many)).payload

    assert len(payload["raises_risk"]) == 3


def _hex_setup(tmp_path: Path) -> tuple[Bundle, list[str]]:
    root = write_bundle(tmp_path / VERSION)
    cells = write_hexes(root)
    return load_bundle(root), cells


@pytest.mark.unit
async def test_area_detail_and_evidence_resolve_from_hexes(
    tmp_path: Path, weather: WeatherService
) -> None:
    bundle, cells = _hex_setup(tmp_path)
    hexes = load_hexes(bundle.root)

    detail = await resolve_area_detail(hexes, bundle, weather, cells[0], NIGHT, "wet")
    evidence = await resolve_area_evidence(hexes, bundle, weather, cells[0], NIGHT, "wet")

    assert detail.cell == cells[0]
    assert detail.condition_used.cond == "wet"
    assert evidence.kind == "area"
    assert evidence.payload["score"] == detail.score
    assert evidence.payload["conditions"] == "wet"


@pytest.mark.unit
async def test_area_resolution_errors(tmp_path: Path, weather: WeatherService) -> None:
    bundle, cells = _hex_setup(tmp_path)
    hexes = load_hexes(bundle.root)

    with pytest.raises(AppError) as missing:
        await resolve_area_detail(None, bundle, weather, cells[0], NIGHT, "dry")
    with pytest.raises(AppError) as outside:
        await resolve_area_detail(hexes, bundle, weather, "8944c1a8c2bffff", NIGHT, "dry")
    with pytest.raises(AppError) as bad_time:
        await resolve_area_detail(hexes, bundle, weather, cells[0], "whenever", "dry")

    assert missing.value.code == "CITY_PULSE_UNAVAILABLE" and missing.value.status == 503
    assert outside.value.code == "OUTSIDE_CITY" and outside.value.status == 404
    assert bad_time.value.code == "BAD_TIME" and bad_time.value.status == 422


# --- live conditions -------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("hour", "light", "label"),
    [(22, "dark", "10 PM"), (12, "daylight", "12 PM"), (7, "twilight", "7 AM")],
)
def test_conditions_evidence_has_time_light_and_wetness(hour: int, light: str, label: str) -> None:
    at = datetime(2026, 9, 25, hour, 15 if hour == 7 else 0, tzinfo=ATLANTA)

    evidence = conditions_evidence(Resolved(True, "override", "Wet (your choice)"), at)

    assert evidence.kind == "conditions"
    assert evidence.payload["time"] == label
    assert evidence.payload["light"] == light
    assert evidence.payload["conditions"] == "wet"
    assert evidence.payload["day"] == "Friday"


@pytest.mark.unit
async def test_resolve_conditions_uses_live_weather(weather: WeatherService) -> None:
    evidence = await resolve_conditions_evidence(weather, NOON, "live")

    assert evidence.payload["conditions"] == "dry"  # forecast unavailable: assumed dry
    assert evidence.payload["time"] == "12 PM"
