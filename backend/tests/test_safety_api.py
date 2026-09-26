"""Safety endpoints, route safety summaries, the route preference, and old-bundle fallback."""

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

from tests.bundle_factory import COLS, HOT_ROW, LAT0, LON0, ROWS, node_id, write_bundle
from tests.safety_factory import HOT_CRIMES, write_safety

BBOX = f"{LON0 - 0.01},{LAT0 - 0.01},{LON0 + 0.02},{LAT0 + 0.01}"
BANNED = ("safe", "unsafe", "dangerous", "bad area")


def _client(root: Path) -> Iterator[TestClient]:
    settings = Settings(artifacts_dir=root, rate_limit_per_minute=1000, _env_file=None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as c:
            yield c


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    root = write_bundle(tmp_path / "pp-test-0001")
    write_safety(root)
    yield from _client(root)


@pytest.fixture
def old_client(bundle_dir: Path) -> Iterator[TestClient]:
    yield from _client(bundle_dir)


def _route_body(client: TestClient, depart: str, **extra: str) -> dict[str, object]:
    g = client.app.state.bundle.graph  # type: ignore[attr-defined]

    def at(n: int) -> dict[str, float]:
        return {"lat": float(g.node_lat[n]), "lon": float(g.node_lon[n])}

    return {
        "origin": at(node_id(HOT_ROW, 0)),
        "destination": at(node_id(HOT_ROW, COLS - 1)),
        "depart_at": depart,
        "cond": "dry",
        **extra,
    }


@pytest.mark.integration
def test_meta_lists_sources_categories_and_day_parts(client: TestClient) -> None:
    body = client.get("/safety/meta").json()

    data = body["data"]
    assert body["success"]
    assert data["data_through"] == "2026-09-26"
    assert data["sources"][0]["license"]
    assert "Robbery" in data["crime_categories"]
    assert [p["key"] for p in data["day_parts"]] == ["night", "morning", "afternoon", "evening"]
    assert data["day_parts"][0]["hours"][0] == 22


@pytest.mark.integration
def test_hexes_follow_the_day_part_of_the_hour(client: TestClient) -> None:
    rows = client.get("/safety/hexes", params={"bbox": BBOX, "hour": 23}).json()["data"]

    assert rows
    hot = max(rows, key=lambda r: r["crimes_persons_12mo"])
    assert hot["crimes_persons_12mo"] == HOT_CRIMES
    assert hot["crime_band"] == "higher"
    assert set(rows[0]) == {
        "h3",
        "lat",
        "lon",
        "crimes_persons_12mo",
        "crime_band",
        "lit_share",
        "activity_band",
        "help_points",
    }
    assert {r["activity_band"] for r in rows} <= {"quiet", "moderate", "busy", None}


@pytest.mark.integration
def test_hexes_outside_the_bbox_are_left_out(client: TestClient) -> None:
    far = "-84.20,33.60,-84.10,33.70"

    assert client.get("/safety/hexes", params={"bbox": far, "hour": 12}).json()["data"] == []


@pytest.mark.integration
@pytest.mark.parametrize(
    "params",
    [
        {"bbox": "-84.9,33.5,-84.1,33.9", "hour": 12},  # wider than 0.3 degrees
        {"bbox": "a,b,c,d", "hour": 12},
        {"bbox": BBOX, "hour": 24},
        {"bbox": BBOX, "hour": -1},
    ],
)
def test_hexes_validate_bbox_and_hour(client: TestClient, params: dict[str, object]) -> None:
    resp = client.get("/safety/hexes", params=params)

    assert resp.status_code == 422
    assert resp.json()["success"] is False


@pytest.mark.integration
def test_help_points_in_view(client: TestClient) -> None:
    rows = client.get("/safety/help-points", params={"bbox": BBOX}).json()["data"]

    assert {r["kind"] for r in rows} == {"police", "blue_light"}  # the hospital is off-view
    assert all(set(r) == {"kind", "name", "lat", "lon"} for r in rows)


@pytest.mark.integration
def test_old_bundle_returns_safety_unavailable(old_client: TestClient) -> None:
    for path, params in (
        ("/safety/meta", {}),
        ("/safety/hexes", {"bbox": BBOX, "hour": 12}),
        ("/safety/help-points", {"bbox": BBOX}),
    ):
        resp = old_client.get(path, params=params)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "SAFETY_UNAVAILABLE"
    assert old_client.get("/healthz").json()["data"]["safety"] == "unavailable"


@pytest.mark.integration
def test_old_bundle_routes_have_null_safety(old_client: TestClient) -> None:
    body = _route_body(old_client, "2026-09-25T22:30", prefer="lit_and_busy")

    data = old_client.post("/routes", json=body).json()["data"]

    assert data["fastest"]["safety"] is None


@pytest.mark.integration
def test_healthz_reports_safety_ok(client: TestClient) -> None:
    assert client.get("/healthz").json()["data"]["safety"] == "ok"


@pytest.mark.integration
def test_routes_carry_safety_summaries(client: TestClient) -> None:
    data = client.post("/routes", json=_route_body(client, "2026-09-25T22:30")).json()["data"]

    fast = data["fastest"]["safety"]
    assert fast["day_part"] == "night"
    assert fast["lit_share"] is None  # the hot middle row has no lighting data
    assert fast["help_points_within_100m"] >= 1  # the police station at the middle node
    assert fast["crimes_persons_nearby"] == HOT_CRIMES
    assert data["pathpro"]["safety"]["lit_share"] == 0.0  # calm top row is unlit


@pytest.mark.integration
def test_lit_and_busy_preference_changes_the_night_route(client: TestClient) -> None:
    default = client.post("/routes", json=_route_body(client, "2026-09-25T22:30")).json()
    lit = client.post(
        "/routes", json=_route_body(client, "2026-09-25T22:30", prefer="lit_and_busy")
    ).json()

    assert lit["data"]["pathpro"]["safety"]["lit_share"] == 1.0
    assert lit["data"]["pathpro"]["safety"]["busy_share"] == 1.0
    assert lit["data"]["route_key"] != default["data"]["route_key"]
    assert lit["data"]["pathpro"]["coords"] != default["data"]["pathpro"]["coords"]
    bottom = client.app.state.bundle.graph.node_lat[node_id(ROWS - 1, 1)]  # type: ignore[attr-defined]
    assert any(abs(c[1] - bottom) < 1e-5 for c in lit["data"]["pathpro"]["coords"])


@pytest.mark.integration
def test_unknown_preference_is_rejected(client: TestClient) -> None:
    resp = client.post("/routes", json=_route_body(client, "now", prefer="safest"))

    assert resp.status_code == 422


@pytest.mark.integration
def test_route_explanation_evidence_leaves_out_safety_signals(client: TestClient) -> None:
    from app.services.explain.evidence import route_evidence

    client.post("/routes", json=_route_body(client, "2026-09-25T22:30"))
    routes = next(iter(client.app.state.routes_cache.values()))  # type: ignore[attr-defined]

    evidence = str(route_evidence(routes))

    assert "crime" not in evidence and "help_points" not in evidence


@pytest.mark.integration
def test_safety_copy_avoids_banned_words(client: TestClient) -> None:
    text = client.get("/safety/meta").text.lower()
    text += client.get("/safety/help-points", params={"bbox": BBOX}).text.lower()

    assert not [w for w in BANNED if f" {w} " in text or f'"{w}' in text]
