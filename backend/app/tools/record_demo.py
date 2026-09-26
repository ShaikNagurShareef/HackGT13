"""Record the scripted demo (PRD DEMO-01) into frontend/public/demo for offline playback.

Usage: cd backend && uv run python -m app.tools.record_demo
Explanations use whatever providers are configured in backend/.env (template otherwise),
so re-run after adding API keys to pre-warm grounded LLM text for the demo.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import BACKEND_DIR, get_settings
from app.main import create_app

DEMO_DIR = BACKEND_DIR.parent / "frontend" / "public" / "demo"
DEPART = "2026-09-25T22:30"
TRIPS = (
    ({"lat": 33.7771, "lon": -84.3962}, {"lat": 33.7810, "lon": -84.3863}),  # Klaus -> Midtown
    ({"lat": 33.7765, "lon": -84.3893}, {"lat": 33.7716, "lon": -84.3872}),  # Tech Sq -> North Ave
)
STATIC_FILES = ("segments.geojson", "hotspot_nodes.json", "hex_cells.json")
RIDE_STATIC_FILES = ("ride_segments.geojson", "ride_hotspot_nodes.json")
RIDE_MODES = ("bike", "ebike", "scooter")
CONDS = ("wet", "dry", "live")
WEST_END = {"lat": 33.7537, "lon": -84.4167}
# Georgia Tech + Midtown: the area the offline demo shows (well under the 0.3° bbox limit).
DEMO_BBOX = "-84.4200,33.7550,-84.3700,33.7950"


def _ok(resp: Any) -> Any:
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"demo request failed: {body.get('error')}")
    return body


def record(client: TestClient) -> dict[str, Any]:
    fixtures: dict[str, Any] = {"GET /meta": _ok(client.get("/meta"))}
    fixtures["GET /conditions/live"] = {
        "success": True,
        "data": {"cond": "wet", "source": "live", "label": "Light rain · demo forecast"},
        "error": None,
        "model_version": fixtures["GET /meta"]["model_version"],
    }
    seg_ids: set[int] = set()
    for cond in ("wet", "dry", "live"):
        for origin, dest in TRIPS:
            body = {"origin": origin, "destination": dest, "depart_at": DEPART, "cond": cond}
            routes = _ok(client.post("/routes", json=body))
            o = f"{origin['lat']:.4f},{origin['lon']:.4f}"
            d = f"{dest['lat']:.4f},{dest['lon']:.4f}"
            key = f"POST /routes {o}>{d}|{cond}"
            fixtures[key] = routes
            data = routes["data"]
            explain = {"kind": "route", "route_key": data["route_key"]}
            fixtures[f"POST /explain route:{data['route_key']}"] = _ok(
                client.post("/explain", json=explain)
            )
            for route in (data["fastest"], data["pathpro"]):
                if route:
                    seg_ids.update(s["seg_id"] for s in route["top_segments"])
    for seg in sorted(seg_ids):
        for cond in ("wet", "dry", "live"):
            params = {"t": DEPART, "cond": cond}
            fixtures[f"GET /segments/{seg}|{cond}"] = _ok(
                client.get(f"/segments/{seg}", params=params)
            )
            body = {"kind": "segment", "seg_id": seg, "t": DEPART, "cond": cond}
            fixtures[f"POST /explain segment:{seg}|{cond}"] = _ok(
                client.post("/explain", json=body)
            )
    for cond in ("wet", "dry", "live"):
        params = {**WEST_END, "t": DEPART, "cond": cond}
        fixtures[f"GET /areas/lookup|{cond}"] = _ok(client.get("/areas/lookup", params=params))
    fixtures.update(record_safety(client))
    fixtures.update(record_ride(client))
    return fixtures


def _ride_available(client: TestClient) -> bool:
    modes = client.get("/meta").json()["data"].get("modes") or []
    return any(m.get("network") == "ride" and m.get("available") for m in modes)


def record_ride(client: TestClient) -> dict[str, Any]:
    """Bike / e-bike / scooter routes, ride street details, and MARTA stations for the demo."""
    out: dict[str, Any] = {"GET /transit/stations": _ok(client.get("/transit/stations"))}
    if not _ride_available(client):
        return out
    seg_ids: set[int] = set()
    for mode in RIDE_MODES:
        for cond in CONDS:
            for origin, dest in TRIPS:
                body = {"origin": origin, "destination": dest, "depart_at": DEPART}
                routes = _ok(client.post("/routes", json={**body, "cond": cond, "mode": mode}))
                o = f"{origin['lat']:.4f},{origin['lon']:.4f}"
                d = f"{dest['lat']:.4f},{dest['lon']:.4f}"
                out[f"POST /routes {o}>{d}|{cond}|{mode}"] = routes
                data = routes["data"]
                explain = {"kind": "route", "route_key": data["route_key"]}
                out[f"POST /explain route:{data['route_key']}"] = _ok(
                    client.post("/explain", json=explain)
                )
                for route in (data["fastest"], data["pathpro"]):
                    if route:
                        seg_ids.update(s["seg_id"] for s in route["top_segments"])
    for seg in sorted(seg_ids):
        for mode in RIDE_MODES:
            for cond in CONDS:
                params = {"t": DEPART, "cond": cond, "mode": mode}
                out[f"GET /segments/{seg}|{cond}|{mode}"] = _ok(
                    client.get(f"/segments/{seg}", params=params)
                )
    return out


def record_safety(client: TestClient) -> dict[str, Any]:
    """Safety layer for the demo area; skipped when the bundle has no safety files."""
    meta = client.get("/safety/meta").json()
    if not meta.get("success"):
        return {}
    out: dict[str, Any] = {"GET /safety/meta": meta}
    out["GET /safety/help-points"] = _ok(
        client.get("/safety/help-points", params={"bbox": DEMO_BBOX})
    )
    for hour in range(24):
        params = {"bbox": DEMO_BBOX, "hour": hour}
        out[f"GET /safety/hexes|{hour}"] = _ok(client.get("/safety/hexes", params=params))
    return out


def copy_static(version: str, artifacts: Path) -> str:
    target = DEMO_DIR / "static" / version
    if (DEMO_DIR / "static").exists():
        shutil.rmtree(DEMO_DIR / "static")
    target.mkdir(parents=True)
    for name in STATIC_FILES:
        shutil.copy2(artifacts / name, target / name)
    for name in RIDE_STATIC_FILES:
        if (artifacts / name).exists():
            shutil.copy2(artifacts / name, target / name)
    frame_files = [
        *artifacts.glob("frames_*.bin"),
        *artifacts.glob("hex_frames_*.bin"),
        *artifacts.glob("ride_frames_*.bin"),
    ]
    for frames in frame_files:
        shutil.copy2(frames, target / frames.name)
    return f"/demo/static/{version}"


def main() -> None:
    settings = get_settings().model_copy(
        update={"rate_limit_per_minute": 1_000_000, "paid_rate_limit_per_minute": 1_000_000}
    )
    app = create_app(settings)
    with TestClient(app) as client:
        fixtures = record(client)
    version = fixtures["GET /meta"]["data"]["model_version"]
    static_base = copy_static(version, app.state.bundle.root)
    fixtures["GET /meta"]["data"]["static_base"] = static_base
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "fixtures.json").write_text(json.dumps(fixtures, separators=(",", ":")))
    print(f"recorded {len(fixtures)} demo responses for {version} -> {DEMO_DIR}")


if __name__ == "__main__":
    main()
