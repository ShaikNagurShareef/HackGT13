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
WEST_END = {"lat": 33.7537, "lon": -84.4167}


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
    return fixtures


def copy_static(version: str, artifacts: Path) -> str:
    target = DEMO_DIR / "static" / version
    if (DEMO_DIR / "static").exists():
        shutil.rmtree(DEMO_DIR / "static")
    target.mkdir(parents=True)
    for name in STATIC_FILES:
        shutil.copy2(artifacts / name, target / name)
    for frames in [*artifacts.glob("frames_*.bin"), *artifacts.glob("hex_frames_*.bin")]:
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
