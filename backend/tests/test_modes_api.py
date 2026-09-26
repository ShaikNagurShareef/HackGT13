"""Multi-mode API: /meta modes, /healthz modes, ride /routes, ride /segments, explanations."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from app.config import Settings
from app.main import create_app
from app.services.weather import FORECAST_URL
from fastapi.testclient import TestClient

from tests.bundle_factory import COLS, HOT_ROW, LAT0, LON0, node_id


def _client(root: Path) -> Iterator[TestClient]:
    settings = Settings(artifacts_dir=root, rate_limit_per_minute=1000, _env_file=None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as c:
            yield c


@pytest.fixture
def walk_client(bundle_dir: Path) -> Iterator[TestClient]:
    yield from _client(bundle_dir)


@pytest.fixture
def ride_client(ride_bundle_dir: Path) -> Iterator[TestClient]:
    yield from _client(ride_bundle_dir)


def _latlon(client: TestClient, node: int) -> dict[str, float]:
    g = client.app.state.bundle.graph  # type: ignore[attr-defined]
    return {"lat": float(g.node_lat[node]), "lon": float(g.node_lon[node])}


def _body(client: TestClient, **extra: object) -> dict[str, object]:
    return {
        "origin": _latlon(client, node_id(HOT_ROW, 0)),
        "destination": _latlon(client, node_id(HOT_ROW, COLS - 1)),
        "depart_at": "2026-09-25T22:30",
        "cond": "dry",
        **extra,
    }


@pytest.mark.integration
def test_meta_lists_modes_with_ride_unavailable_on_a_walk_only_bundle(
    walk_client: TestClient,
) -> None:
    data = walk_client.get("/meta").json()["data"]

    modes = {m["key"]: m for m in data["modes"]}
    assert list(modes) == ["walk", "bike", "ebike", "scooter"]
    assert modes["walk"]["available"] is True
    assert modes["walk"]["network"] == "walk" and modes["walk"]["static_prefix"] == ""
    assert not any(modes[k]["available"] for k in ("bike", "ebike", "scooter"))
    assert data["ride_model"] is None


@pytest.mark.integration
def test_meta_and_health_report_ride_when_the_ride_model_loads(ride_client: TestClient) -> None:
    meta = ride_client.get("/meta").json()["data"]
    health = ride_client.get("/healthz").json()["data"]

    bike = next(m for m in meta["modes"] if m["key"] == "bike")
    assert bike == {
        "key": "bike",
        "label": "Bike",
        "available": True,
        "speed_kmh": 15,
        "network": "ride",
        "static_prefix": "ride_",
    }
    assert meta["ride_model"] == {"capture_top10": 0.41, "roc_auc": 0.83}
    assert health["modes"] == {"walk": "ok", "ride": "ok"}


@pytest.mark.integration
def test_health_reports_ride_unavailable_without_ride_files(walk_client: TestClient) -> None:
    health = walk_client.get("/healthz").json()["data"]

    assert health["modes"] == {"walk": "ok", "ride": "unavailable"}


@pytest.mark.integration
def test_ride_mode_on_walk_only_bundle_is_503_mode_unavailable(walk_client: TestClient) -> None:
    resp = walk_client.post("/routes", json=_body(walk_client, mode="scooter"))

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODE_UNAVAILABLE"


@pytest.mark.integration
def test_bike_route_uses_ride_graph_speed_and_ignores_lit_preference(
    ride_client: TestClient,
) -> None:
    walk = ride_client.post("/routes", json=_body(ride_client)).json()["data"]
    bike = ride_client.post(
        "/routes", json=_body(ride_client, mode="bike", prefer="lit_and_busy")
    ).json()["data"]

    assert walk["mode"] == "walk" and bike["mode"] == "bike"
    assert bike["prefer"] == "lower_traffic_risk"
    fastest = bike["fastest"]
    assert fastest["duration_s"] == pytest.approx(fastest["distance_m"] / (15 / 3.6), rel=0.01)
    assert fastest["duration_s"] < walk["fastest"]["duration_s"]
    assert bike["pathpro"] is not None
    assert bike["fastest"]["safety"] is None
    # The 4-column ride grid numbers its segments differently from the 3-column walk grid.
    assert bike["pathpro"]["segment_ids"] != walk["pathpro"]["segment_ids"]
    assert bike["route_key"] != walk["route_key"]


@pytest.mark.integration
def test_walk_route_key_is_unchanged_by_an_explicit_walk_mode(ride_client: TestClient) -> None:
    implicit = ride_client.post("/routes", json=_body(ride_client)).json()["data"]
    explicit = ride_client.post("/routes", json=_body(ride_client, mode="walk")).json()["data"]

    assert implicit["route_key"] == explicit["route_key"]
    assert implicit["prefer"] == "lower_traffic_risk"


@pytest.mark.integration
def test_each_ride_mode_has_its_own_duration(ride_client: TestClient) -> None:
    durations = {
        mode: ride_client.post("/routes", json=_body(ride_client, mode=mode)).json()["data"][
            "fastest"
        ]["duration_s"]
        for mode in ("bike", "ebike", "scooter")
    }

    assert durations["ebike"] < durations["scooter"] < durations["bike"]


@pytest.mark.integration
def test_unknown_mode_is_rejected(ride_client: TestClient) -> None:
    resp = ride_client.post("/routes", json=_body(ride_client, mode="car"))

    assert resp.status_code == 422


@pytest.mark.integration
def test_ride_segment_ids_refer_to_the_ride_bundle(ride_client: TestClient) -> None:
    ride = ride_client.get("/segments/15", params={"mode": "bike", "t": "2026-09-25T22:30"})
    walk = ride_client.get("/segments/15", params={"t": "2026-09-25T22:30"})

    assert ride.status_code == 200
    assert ride.json()["data"]["mode"] == "bike"
    assert walk.status_code == 404


@pytest.mark.integration
def test_ride_segment_on_walk_only_bundle_is_503(walk_client: TestClient) -> None:
    resp = walk_client.get("/segments/1", params={"mode": "ebike"})

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODE_UNAVAILABLE"


@pytest.mark.integration
def test_hourly_history_stays_walk_only(ride_client: TestClient) -> None:
    resp = ride_client.get("/segments/15/hourly", params={"mode": "bike"})

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.integration
def test_ride_route_explanation_talks_about_riding(ride_client: TestClient) -> None:
    key = ride_client.post("/routes", json=_body(ride_client, mode="bike")).json()["data"][
        "route_key"
    ]

    data = ride_client.post("/explain", json={"kind": "route", "route_key": key}).json()["data"]

    assert data["source"] == "template"
    assert "ride" in data["text"].lower()
    assert "PathPro route" in data["text"]


@pytest.mark.integration
def test_ride_segment_explanation_uses_the_ride_bundle(ride_client: TestClient) -> None:
    body = {"kind": "segment", "seg_id": 15, "mode": "scooter", "t": "2026-09-25T22:30"}

    data = ride_client.post("/explain", json=body).json()["data"]

    assert "bikes and scooters" in data["text"]
    assert "pedestrian" not in data["text"].lower()


@pytest.mark.integration
def test_transit_stations_are_inside_the_coverage_bbox(walk_client: TestClient) -> None:
    data = walk_client.get("/transit/stations").json()["data"]

    west, south, east, north = [-84.415, 33.745, -84.370, 33.795]
    names = {s["name"] for s in data}
    assert "Five Points" in names and "Midtown" in names
    assert "Inman Park/Reynoldstown" not in names  # east of the test bundle's bbox
    assert all(west <= s["lon"] <= east and south <= s["lat"] <= north for s in data)
    assert all(isinstance(s["lines"], list) for s in data)
    assert abs(LAT0 - 33.776) < 0.01 and abs(LON0 + 84.396) < 0.01
