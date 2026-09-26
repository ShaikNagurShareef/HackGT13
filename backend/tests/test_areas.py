"""City Pulse area endpoints (CITY-01..04)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from app.config import Settings
from app.main import create_app
from app.services.weather import FORECAST_URL
from fastapi.testclient import TestClient

from tests.bundle_factory import LAT0, LON0, write_bundle, write_hexes


@pytest.fixture
def hex_client(tmp_path: Path) -> Iterator[tuple[TestClient, list[str]]]:
    root = write_bundle(tmp_path / "pp-test-0001")
    cells = write_hexes(root)
    settings = Settings(artifacts_dir=root, _env_file=None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as c:
            yield c, cells


@pytest.mark.integration
def test_area_lookup_factors_sum_to_score(hex_client: tuple[TestClient, list[str]]) -> None:
    client, cells = hex_client

    data = client.get(
        "/areas/lookup", params={"lat": LAT0, "lon": LON0, "t": "2026-09-25T22:30", "cond": "wet"}
    ).json()["data"]

    assert data["cell"] == cells[0]
    parts = (
        data["baseline_points"]
        + sum(f["points"] for f in data["factors"])
        + data["remainder_points"]
    )
    assert parts == data["score"]
    assert data["in_street_coverage"] is True
    assert data["confidence"] == "high"


@pytest.mark.integration
def test_night_scores_at_least_day(hex_client: tuple[TestClient, list[str]]) -> None:
    client, cells = hex_client

    night = client.get(f"/areas/{cells[0]}", params={"t": "2026-09-25T23:00", "cond": "dry"})
    noon = client.get(f"/areas/{cells[0]}", params={"t": "2026-09-25T12:00", "cond": "dry"})

    assert night.json()["data"]["score"] >= noon.json()["data"]["score"]


@pytest.mark.integration
def test_outside_city_and_bad_cell(hex_client: tuple[TestClient, list[str]]) -> None:
    client, _ = hex_client

    far = client.get("/areas/lookup", params={"lat": 40.0, "lon": -75.0})
    bad = client.get("/areas/not-a-cell")

    assert far.json()["error"]["code"] == "OUTSIDE_CITY"
    assert bad.status_code == 422


@pytest.mark.integration
def test_city_pulse_absent_returns_503(bundle_dir: Path, tmp_path: Path) -> None:
    root = tmp_path / "plain"
    shutil.copytree(bundle_dir, root)
    with TestClient(create_app(Settings(artifacts_dir=root, _env_file=None))) as c:
        resp = c.get("/areas/lookup", params={"lat": LAT0, "lon": LON0})

    assert resp.status_code == 503
