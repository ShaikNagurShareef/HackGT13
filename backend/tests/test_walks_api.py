"""Share-my-walk endpoints: create, owner-only position updates, follower reads, expiry, limits."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from app.api.walks import get_clock
from app.config import Settings
from app.main import create_app
from app.middleware import is_paid
from app.repositories.walks import WalksRepository
from app.services.weather import FORECAST_URL
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from tests.fake_mongo import FakeCollection

T0 = datetime(2026, 9, 26, 22, 30, tzinfo=UTC)
DEST = {"label": "Midtown MARTA", "lat": 33.781, "lon": -84.3863}
ROUTE = [[-84.3962, 33.7771], [-84.39, 33.779], [-84.3863, 33.781]]
HERE = {"lat": 33.7775, "lon": -84.395}


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(bundle_dir: Path, clock: Clock) -> Iterator[TestClient]:
    settings = Settings(artifacts_dir=bundle_dir, rate_limit_per_minute=1000, _env_file=None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.route(host="testserver").pass_through()
        app = create_app(settings)
        app.dependency_overrides[get_clock] = lambda: clock
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


@pytest.fixture
def fake(client: TestClient) -> FakeCollection:
    coll = FakeCollection()
    client.app.state.walks = WalksRepository(None, collection=coll)  # type: ignore[attr-defined]
    return coll


def _create(client: TestClient, **extra: object) -> dict[str, str]:
    body: dict[str, object] = {"destination": DEST, "eta_s": 720, "route": ROUTE, **extra}
    resp = client.post("/walks", json=body)
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


def _put(client: TestClient, walk_id: str, token: str, **fields: object) -> httpx.Response:
    return client.put(f"/walks/{walk_id}/position", json={"owner_token": token, **HERE, **fields})


@pytest.mark.integration
def test_create_returns_unguessable_ids_and_stores_only_a_token_hash(
    client: TestClient, fake: FakeCollection
) -> None:
    first = _create(client)
    second = _create(client)

    walk_id, token = first["walk_id"], first["owner_token"]
    assert len(walk_id) >= 16 and walk_id.replace("-", "").replace("_", "").isalnum()
    assert len(token) >= 22
    assert walk_id != second["walk_id"] and token != second["owner_token"]
    assert first["follow_path"] == f"/follow/{walk_id}"
    assert datetime.fromisoformat(first["expires_at"]) == T0 + timedelta(hours=6)
    stored = fake.docs[0]
    assert stored["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in repr(fake.docs)


@pytest.mark.integration
def test_follower_sees_destination_route_and_eta_but_never_the_token(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    clock.advance(60)

    resp = client.get(f"/walks/{created['walk_id']}")

    data = resp.json()["data"]
    assert resp.status_code == 200
    assert data["status"] == "walking"
    assert data["destination"] == DEST
    assert data["route"] == ROUTE
    assert data["position"] is None
    assert data["eta_s"] == 660  # 12 min at creation, one minute later
    assert datetime.fromisoformat(data["eta_at"]) == T0 + timedelta(seconds=720)
    assert "token" not in resp.text and created["owner_token"] not in resp.text
    assert fake.docs[0]["token_hash"] not in resp.text


@pytest.mark.integration
def test_owner_posts_positions_and_the_follower_sees_them(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    clock.advance(5)

    resp = _put(client, created["walk_id"], created["owner_token"], accuracy_m=9.5, eta_s=600)
    data = client.get(f"/walks/{created['walk_id']}").json()["data"]

    assert resp.status_code == 200
    summary = resp.json()["data"]
    assert "route" not in summary
    assert summary["position"]["lat"] == HERE["lat"]
    assert data["position"] == {
        "lat": HERE["lat"],
        "lon": HERE["lon"],
        "accuracy_m": 9.5,
        "at": data["updated_at"],
    }
    assert datetime.fromisoformat(data["updated_at"]) == T0 + timedelta(seconds=5)
    assert datetime.fromisoformat(data["expires_at"]) == T0 + timedelta(hours=6, seconds=5)
    assert data["eta_s"] == 600


@pytest.mark.integration
def test_wrong_token_is_rejected_and_nothing_changes(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    clock.advance(5)

    resp = _put(client, created["walk_id"], "x" * 43)

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "WALK_FORBIDDEN"
    assert client.get(f"/walks/{created['walk_id']}").json()["data"]["position"] is None


@pytest.mark.integration
@pytest.mark.parametrize("walk_id", ["A" * 22, "short", "has.dots.in.it.xxxxxxxxx", "x" * 80])
def test_unknown_or_malformed_walks_are_not_found(
    client: TestClient, fake: FakeCollection, walk_id: str
) -> None:
    got = client.get(f"/walks/{walk_id}")
    put = _put(client, walk_id, "t" * 43)

    for resp in (got, put):
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "WALK_NOT_FOUND"


@pytest.mark.integration
def test_updates_faster_than_every_three_seconds_are_throttled_politely(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    walk_id, token = created["walk_id"], created["owner_token"]
    clock.advance(5)
    assert _put(client, walk_id, token).status_code == 200

    clock.advance(1)
    fast = _put(client, walk_id, token, lat=33.778)
    clock.advance(0.5)
    status_change = _put(client, walk_id, token, status="arrived")
    clock.advance(3)
    later = _put(client, walk_id, token, lat=33.7785, status="arrived")

    assert fast.status_code == 429
    assert fast.json()["error"]["code"] == "WALK_THROTTLED"
    assert "moment" in fast.json()["error"]["message"]
    assert status_change.status_code == 200  # a status change is never throttled
    assert status_change.json()["data"]["status"] == "arrived"
    assert later.status_code == 200
    assert later.json()["data"]["position"]["lat"] == 33.7785


@pytest.mark.integration
def test_updates_after_the_walk_ended_are_ignored(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    walk_id, token = created["walk_id"], created["owner_token"]
    clock.advance(5)
    ended = _put(client, walk_id, token, status="ended").json()["data"]
    clock.advance(10)

    resp = _put(client, walk_id, token, lat=33.79, status="walking")

    assert resp.status_code == 200
    assert resp.json()["data"] == ended
    assert client.get(f"/walks/{walk_id}").json()["data"]["status"] == "ended"


@pytest.mark.integration
def test_walks_expire_six_hours_after_the_last_update(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    walk_id, token = created["walk_id"], created["owner_token"]
    clock.advance(3600)
    assert _put(client, walk_id, token).status_code == 200

    clock.advance(6 * 3600 - 1)
    assert client.get(f"/walks/{walk_id}").status_code == 200
    clock.advance(2)
    gone = client.get(f"/walks/{walk_id}")

    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "WALK_NOT_FOUND"
    assert "expired" in gone.json()["error"]["message"]
    assert _put(client, walk_id, token).status_code == 404


@pytest.mark.integration
def test_positions_outside_atlanta_are_rejected(
    client: TestClient, fake: FakeCollection, clock: Clock
) -> None:
    created = _create(client)
    clock.advance(5)

    resp = _put(client, created["walk_id"], created["owner_token"], lat=40.7128, lon=-74.006)

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OUTSIDE_AREA"
    assert "Atlanta" in resp.json()["error"]["message"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "body",
    [
        {"destination": {**DEST, "lat": 40.7}, "eta_s": 600},
        {"destination": DEST, "eta_s": 600, "route": [[-74.0, 40.7], [-84.39, 33.78]]},
        {"destination": DEST, "eta_s": 600, "route": [[-84.39, 33.78]] * 2001},
        {"destination": DEST, "eta_s": -1},
        {"destination": DEST, "eta_s": 600, "owner_token": "mine"},
        {"destination": {**DEST, "label": ""}, "eta_s": 600},
        {"destination": {**DEST, "label": "x" * 200}, "eta_s": 600},
        {"destination": DEST, "eta_s": 600, "route": [[-84.39]]},
    ],
)
def test_create_validates_its_input(
    client: TestClient, fake: FakeCollection, body: dict[str, object]
) -> None:
    resp = client.post("/walks", json=body)

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] in {"BAD_REQUEST", "OUTSIDE_AREA"}
    assert fake.docs == []


@pytest.mark.integration
def test_route_is_optional(client: TestClient, fake: FakeCollection) -> None:
    resp = client.post("/walks", json={"destination": DEST, "eta_s": 300})
    walk_id = resp.json()["data"]["walk_id"]

    assert resp.status_code == 201
    assert client.get(f"/walks/{walk_id}").json()["data"]["route"] is None


@pytest.mark.integration
@pytest.mark.parametrize(
    "fields",
    [
        {"status": "teleported"},
        {"accuracy_m": -3},
        {"eta_s": -5},
        {"note": "extra fields are refused"},
    ],
)
def test_position_updates_validate_their_input(
    client: TestClient, fake: FakeCollection, clock: Clock, fields: dict[str, object]
) -> None:
    created = _create(client)
    clock.advance(5)

    resp = _put(client, created["walk_id"], created["owner_token"], **fields)

    assert resp.status_code == 422


@pytest.mark.integration
def test_everything_is_a_503_without_mongodb(client: TestClient) -> None:
    responses = [
        client.post("/walks", json={"destination": DEST, "eta_s": 600}),
        client.get("/walks/" + "a" * 22),
        _put(client, "a" * 22, "t" * 43),
    ]

    for resp in responses:
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "WALKS_UNAVAILABLE"
        assert "Live sharing" in resp.json()["error"]["message"]
    health = client.get("/healthz").json()["data"]
    assert "walks" not in health


@pytest.mark.integration
def test_atlas_outage_is_a_503_not_a_crash(client: TestClient, fake: FakeCollection) -> None:
    fake.fail = ServerSelectionTimeoutError("down")

    resp = client.post("/walks", json={"destination": DEST, "eta_s": 600})

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "WALKS_UNAVAILABLE"


@pytest.mark.integration
def test_a_lost_update_race_is_throttled_not_overwritten(
    client: TestClient, fake: FakeCollection, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create(client)
    clock.advance(5)
    repo = client.app.state.walks  # type: ignore[attr-defined]
    monkeypatch.setattr(repo, "save_update", AsyncMock(return_value=None))  # another update won

    resp = _put(client, created["walk_id"], created["owner_token"])

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "WALK_THROTTLED"


@pytest.mark.integration
def test_cors_allows_put_for_position_updates(client: TestClient) -> None:
    resp = client.options(
        "/walks/abc/position",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"},
    )

    assert resp.status_code == 200


@pytest.mark.unit
def test_creating_walks_uses_the_tighter_limit_but_following_does_not() -> None:
    assert is_paid("POST", "/walks")
    assert not is_paid("GET", "/walks/abc")
    assert not is_paid("PUT", "/walks/abc/position")


@pytest.mark.unit
def test_position_updates_use_the_tighter_write_limit() -> None:
    from app.middleware import is_paid

    assert is_paid("PUT", "/walks/abc123/position")
    assert not is_paid("GET", "/walks/abc123")
