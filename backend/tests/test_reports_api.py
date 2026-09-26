"""Community street report endpoints, route integration, health, and rate limits."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from app.config import Settings
from app.main import create_app
from app.middleware import is_paid
from app.repositories.reports import ReportsRepository
from app.services.weather import FORECAST_URL
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from tests.bundle_factory import COLS, DLAT, DLON, HOT_ROW, LAT0, LON0, node_id
from tests.fake_mongo import FakeCollection

HOT_SEG = 2  # "Row 1 St": node (1,0) -> (1,1), on the fastest route only
CALM_SEG = 0  # "Row 0 St": on the lower-risk detour
BBOX = f"{LON0 - 0.01},{LAT0 - 0.01},{LON0 + 0.01},{LAT0 + 0.01}"


@pytest.fixture
def client(bundle_dir: Path) -> Iterator[TestClient]:
    settings = Settings(artifacts_dir=bundle_dir, rate_limit_per_minute=1000, _env_file=None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as c:
            yield c


@pytest.fixture
def fake(client: TestClient) -> FakeCollection:
    coll = FakeCollection()
    client.app.state.reports = ReportsRepository(None, collection=coll)  # type: ignore[attr-defined]
    return coll


def _post(client: TestClient, seg_id: int, category: str = "construction") -> httpx.Response:
    return client.post("/reports", json={"seg_id": seg_id, "category": category})


@pytest.mark.integration
def test_report_is_located_server_side_and_confirmations_accumulate(
    client: TestClient, fake: FakeCollection
) -> None:
    first = _post(client, HOT_SEG).json()
    second = _post(client, HOT_SEG).json()

    assert first["success"] and first["data"]["confirmations"] == 1
    data = second["data"]
    assert data["confirmations"] == 2
    assert data["street"] == "Row 1 St"
    assert data["label"] == "Construction detour"
    assert data["lon"] == pytest.approx(LON0 + DLON / 2, abs=1e-6)
    assert data["lat"] == pytest.approx(LAT0 + DLAT, abs=1e-6)
    assert data["expires_at"] > data["updated_at"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "body",
    [
        {"seg_id": HOT_SEG, "category": "crime"},
        {"seg_id": HOT_SEG, "category": "construction", "note": "free text is not accepted"},
        {"seg_id": HOT_SEG, "category": "construction", "lon": 0, "lat": 0},
        {"seg_id": -1, "category": "construction"},
    ],
)
def test_report_rejects_unknown_categories_and_client_fields(
    client: TestClient, fake: FakeCollection, body: dict[str, object]
) -> None:
    resp = client.post("/reports", json=body)

    assert resp.status_code == 422
    assert fake.docs == []


@pytest.mark.integration
def test_report_on_unknown_segment_is_404(client: TestClient, fake: FakeCollection) -> None:
    resp = _post(client, 9999)

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.integration
def test_reports_in_viewport_segment_and_summary(client: TestClient, fake: FakeCollection) -> None:
    _post(client, HOT_SEG, "signal_out")
    _post(client, HOT_SEG, "signal_out")
    _post(client, CALM_SEG, "poor_lighting")

    in_view = client.get("/reports", params={"bbox": BBOX}).json()["data"]
    on_seg = client.get(f"/segments/{HOT_SEG}/reports").json()["data"]
    summary = client.get("/reports/summary").json()["data"]

    assert {r["seg_id"] for r in in_view} == {HOT_SEG, CALM_SEG}
    assert [(r["category"], r["confirmations"]) for r in on_seg] == [("signal_out", 2)]
    assert summary[0] == {
        "category": "signal_out",
        "label": "Crossing signal out",
        "reports": 1,
        "confirmations": 2,
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    "bbox",
    [
        "",
        "1,2,3",
        "a,b,c,d",
        "-84.3,33.7,-84.4,33.8",  # min > max
        "-84.9,33.0,-84.1,33.9",  # wider than a city viewport
        "nan,1,2,3",
        "0,95,1,96",  # latitude out of range
    ],
)
def test_bad_or_oversized_bbox_is_rejected(
    client: TestClient, fake: FakeCollection, bbox: str
) -> None:
    resp = client.get("/reports", params={"bbox": bbox})

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] in {"BAD_BBOX", "BAD_REQUEST"}


@pytest.mark.integration
def test_unknown_segment_reports_404(client: TestClient, fake: FakeCollection) -> None:
    assert client.get("/segments/9999/reports").status_code == 404


@pytest.mark.integration
def test_everything_reports_unavailable_without_mongodb(client: TestClient) -> None:
    responses = [
        _post(client, HOT_SEG),
        client.get("/reports", params={"bbox": BBOX}),
        client.get("/reports/summary"),
        client.get(f"/segments/{HOT_SEG}/reports"),
    ]

    for resp in responses:
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "REPORTS_UNAVAILABLE"
        assert "Community reports" in resp.json()["error"]["message"]
    assert client.get("/healthz").json()["data"]["reports"] == "not_configured"


@pytest.mark.integration
def test_atlas_outage_is_a_503_not_a_crash(client: TestClient, fake: FakeCollection) -> None:
    fake.fail = ServerSelectionTimeoutError("down")

    resp = _post(client, HOT_SEG)
    health = client.get("/healthz").json()["data"]

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "REPORTS_UNAVAILABLE"
    assert health["reports"] == "unavailable"
    assert health["status"] == "degraded"


@pytest.mark.integration
def test_healthz_reports_ok_with_atlas(client: TestClient, fake: FakeCollection) -> None:
    health = client.get("/healthz").json()["data"]

    assert health["reports"] == "ok"
    assert health["status"] == "ok"


def _hot_route(client: TestClient) -> dict[str, object]:
    g = client.app.state.bundle.graph  # type: ignore[attr-defined]
    a, b = node_id(HOT_ROW, 0), node_id(HOT_ROW, COLS - 1)
    return {
        "origin": {"lat": float(g.node_lat[a]), "lon": float(g.node_lon[a])},
        "destination": {"lat": float(g.node_lat[b]), "lon": float(g.node_lon[b])},
        "depart_at": "2026-09-25T22:30",
        "cond": "wet",
    }


@pytest.mark.integration
def test_routes_carry_reports_for_the_chosen_route_only(
    client: TestClient, fake: FakeCollection
) -> None:
    _post(client, CALM_SEG, "construction")
    _post(client, HOT_SEG, "signal_out")

    data = client.post("/routes", json=_hot_route(client)).json()["data"]

    assert data["pathpulse"] is not None
    assert [(r["seg_id"], r["category"]) for r in data["reports"]] == [(CALM_SEG, "construction")]


@pytest.mark.integration
def test_reports_never_reach_explanation_evidence(client: TestClient, fake: FakeCollection) -> None:
    _post(client, CALM_SEG, "construction")
    key = client.post("/routes", json=_hot_route(client)).json()["data"]["route_key"]

    text = client.post("/explain", json={"kind": "route", "route_key": key}).json()["data"]["text"]

    assert "Construction" not in text and "report" not in text.lower()


@pytest.mark.integration
def test_routes_still_work_when_reports_fail(client: TestClient, fake: FakeCollection) -> None:
    fake.fail = ServerSelectionTimeoutError("down")

    resp = client.post("/routes", json=_hot_route(client))

    assert resp.status_code == 200
    assert resp.json()["data"]["reports"] == []


@pytest.mark.integration
def test_routes_without_mongodb_have_empty_reports(client: TestClient) -> None:
    data = client.post("/routes", json=_hot_route(client)).json()["data"]

    assert data["reports"] == []


@pytest.mark.unit
def test_rate_limit_rules_are_method_aware() -> None:
    assert is_paid("POST", "/reports")
    assert not is_paid("GET", "/reports")
    assert not is_paid("GET", "/reports/summary")
    assert is_paid("GET", "/geocode")
    assert is_paid("POST", "/explain")
    assert not is_paid("POST", "/routes")


@pytest.mark.integration
def test_posting_reports_uses_the_paid_limit_but_viewing_does_not(bundle_dir: Path) -> None:
    settings = Settings(
        artifacts_dir=bundle_dir,
        rate_limit_per_minute=6,
        paid_rate_limit_per_minute=1,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as c:
        c.app.state.reports = ReportsRepository(None, collection=FakeCollection())  # type: ignore[attr-defined]
        posts = [_post(c, HOT_SEG).status_code for _ in range(2)]
        views = [c.get("/reports", params={"bbox": BBOX}).status_code for _ in range(3)]

    assert posts == [200, 429]
    assert views == [200, 200, 200]
