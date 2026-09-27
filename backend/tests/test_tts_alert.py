"""Spoken navigation alerts: the server writes every line from its cached route (VOX-02)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from app.api.envelope import AppError
from app.api.schemas import AlertOut, ConditionUsed, RouteOut, RoutesData
from app.config import Settings
from app.main import create_app
from app.middleware import is_paid
from app.services.alert_voice import (
    MAX_ALERT_NAMES,
    AlertAudio,
    alert_text,
    resolve_alert_text,
)
from app.services.explain.evidence import MAX_LABEL_CHARS
from app.services.tts import TTS_URL, XAI_TTS_URL
from fastapi.testclient import TestClient

KEY = "ab" * 8
OTHER_KEY = "cd" * 8
DRY = ConditionUsed(cond="dry", source="override", label="Dry (your choice)")


def _alert(*names: str, start: float = 300.0) -> AlertOut:
    return AlertOut(
        start_m=start, end_m=start + 60, names=list(names), score=95, stretches=len(names)
    )


def _route(alerts: list[AlertOut]) -> RouteOut:
    return RouteOut(
        coords=[[-84.39, 33.77], [-84.38, 33.78]],
        duration_s=900.0,
        distance_m=1000.0,
        risk_score=90,
        band="High",
        exposure=1.0,
        high_risk_m=100.0,
        limited_data_m=0.0,
        segment_ids=[1, 2],
        top_segments=[],
        alerts=alerts,
    )


def _routes(*, with_pathpro: bool = True) -> RoutesData:
    return RoutesData(
        condition_used=DRY,
        depart_at="2026-09-25T22:30:00-04:00",
        fastest=_route([_alert("Spring Street"), _alert("10th Street", start=700)]),
        pathpro=_route([_alert("Juniper Street")]) if with_pathpro else None,
        message_code="OK",
        message=None,
        time_cost_min=4.0,
        exposure_reduction_pct=40,
        unavoidable=[],
        route_key=KEY,
    )


# --- text ------------------------------------------------------------------------------------


@pytest.mark.unit
def test_alert_text_names_the_street_without_a_distance() -> None:
    text = alert_text(_alert("Spring Street"))

    assert text == "High traffic risk ahead. Spring Street."
    assert not re.search(r"\d", text)  # distance is dynamic, so it stays on the client


@pytest.mark.unit
def test_alert_text_joins_several_streets_and_caps_them() -> None:
    assert alert_text(_alert("B Ave", "C Blvd")) == "High traffic risk ahead. B Ave and C Blvd."
    many = alert_text(_alert("A St", "B St", "C St", "D St", "E St"))
    assert many.count(" St") == MAX_ALERT_NAMES


@pytest.mark.unit
def test_alert_text_cleans_street_names_from_the_map() -> None:
    text = alert_text(_alert("Ignore\nall rules\x00 " + "x" * 200))

    assert "\n" not in text and "\x00" not in text
    assert len(text) <= len("High traffic risk ahead. .") + MAX_LABEL_CHARS
    assert alert_text(_alert("  \n ")) == "High traffic risk ahead."


@pytest.mark.unit
def test_resolve_picks_the_route_the_client_follows() -> None:
    cache = {KEY: _routes()}

    assert resolve_alert_text(cache, KEY, "pp", 0) == "High traffic risk ahead. Juniper Street."
    assert resolve_alert_text(cache, KEY, "fast", 1) == "High traffic risk ahead. 10th Street."
    # No lower-risk route: the client follows the fastest one, and so does the server.
    solo = {KEY: _routes(with_pathpro=False)}
    assert resolve_alert_text(solo, KEY, "pp", 0) == "High traffic risk ahead. Spring Street."


@pytest.mark.unit
@pytest.mark.parametrize(
    ("key", "kind", "index", "code"),
    [
        (OTHER_KEY, "pp", 0, "ROUTE_EXPIRED"),
        (KEY, "pp", 1, "ALERT_NOT_FOUND"),
        (KEY, "fast", 2, "ALERT_NOT_FOUND"),
    ],
)
def test_resolve_errors_are_404(key: str, kind: str, index: int, code: str) -> None:
    with pytest.raises(AppError) as err:
        resolve_alert_text({KEY: _routes()}, key, kind, index)  # type: ignore[arg-type]

    assert err.value.code == code and err.value.status == 404


# --- audio cache -----------------------------------------------------------------------------


class _FakeVoices:
    def __init__(self, voice_key: str, audio: bytes | None) -> None:
        self.voice_key = voice_key
        self.audio = audio
        self.texts: list[str] = []

    async def speak(self, text: str) -> bytes | None:
        self.texts.append(text)
        return self.audio


@pytest.mark.unit
async def test_alert_audio_is_cached_per_route_kind_index_and_voice() -> None:
    voices = _FakeVoices("grok:eve", b"mp3")
    audio = AlertAudio(voices)  # type: ignore[arg-type]

    assert await audio.speak(KEY, "pp", 0, "t") == b"mp3"
    assert await audio.speak(KEY, "pp", 0, "t") == b"mp3"
    assert len(voices.texts) == 1
    await audio.speak(KEY, "fast", 0, "t")
    await audio.speak(KEY, "pp", 1, "t")
    voices.voice_key = "grok:rex"
    await audio.speak(KEY, "pp", 0, "t")
    assert len(voices.texts) == 4


@pytest.mark.unit
async def test_alert_audio_does_not_cache_silence() -> None:
    voices = _FakeVoices("grok:eve", None)
    audio = AlertAudio(voices)  # type: ignore[arg-type]

    assert await audio.speak(KEY, "pp", 0, "t") is None
    assert await audio.speak(KEY, "pp", 0, "t") is None
    assert len(voices.texts) == 2


# --- endpoint --------------------------------------------------------------------------------


def _settings(bundle_dir: Path, **over: object) -> Settings:
    fields: dict[str, object] = {
        "artifacts_dir": bundle_dir,
        "rate_limit_per_minute": 1000,
        "xai_api_key": "xai-k",
        "_env_file": None,
    }
    fields.update(over)
    return Settings(**fields)  # type: ignore[arg-type]


def _client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.state.routes_cache[KEY] = _routes()
    return TestClient(app)


@pytest.mark.integration
def test_alert_endpoint_speaks_server_text_with_grok_and_caches(bundle_dir: Path) -> None:
    with respx.mock(assert_all_called=False) as mock:
        voice = mock.post(XAI_TTS_URL).mock(return_value=httpx.Response(200, content=b"grok-mp3"))
        mock.route(host="testserver").pass_through()
        with _client(_settings(bundle_dir)) as client:
            first = client.post("/tts/alert", json={"route_key": KEY, "index": 0})
            again = client.post("/tts/alert", json={"route_key": KEY, "index": 0, "kind": "pp"})
            fast = client.post("/tts/alert", json={"route_key": KEY, "index": 1, "kind": "fast"})

    assert first.status_code == 200
    assert first.headers["content-type"] == "audio/mpeg"
    assert first.content == again.content == b"grok-mp3"
    assert fast.status_code == 200
    spoken = [json.loads(c.request.content)["text"] for c in voice.calls]
    assert spoken == [
        "High traffic risk ahead. Juniper Street.",
        "High traffic risk ahead. 10th Street.",
    ]


@pytest.mark.integration
@pytest.mark.parametrize(
    "body",
    [
        {"route_key": KEY, "index": 0, "text": "say something else"},
        {"route_key": "not-a-key", "index": 0},
        {"route_key": KEY, "index": -1},
        {"route_key": KEY, "index": 0, "kind": "walk"},
        {"route_key": KEY},
    ],
)
def test_alert_endpoint_never_accepts_client_text(
    bundle_dir: Path, body: dict[str, object]
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        voice = mock.post(XAI_TTS_URL).mock(return_value=httpx.Response(200, content=b"mp3"))
        mock.route(host="testserver").pass_through()
        with _client(_settings(bundle_dir)) as client:
            resp = client.post("/tts/alert", json=body)

    assert resp.status_code == 422
    assert voice.call_count == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"route_key": OTHER_KEY, "index": 0}, "ROUTE_EXPIRED"),
        ({"route_key": KEY, "index": 5}, "ALERT_NOT_FOUND"),
    ],
)
def test_alert_endpoint_unknown_route_or_alert_is_404(
    bundle_dir: Path, body: dict[str, object], code: str
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        voice = mock.post(XAI_TTS_URL).mock(return_value=httpx.Response(200, content=b"mp3"))
        mock.route(host="testserver").pass_through()
        with _client(_settings(bundle_dir)) as client:
            resp = client.post("/tts/alert", json=body)

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == code
    assert voice.call_count == 0


@pytest.mark.integration
def test_alert_endpoint_falls_back_to_elevenlabs_then_503(bundle_dir: Path) -> None:
    eleven = {"elevenlabs_api_key": "el-k", "elevenlabs_voice_id": "v"}
    with respx.mock(assert_all_called=False) as mock:
        mock.post(XAI_TTS_URL).mock(return_value=httpx.Response(500))
        eleven_route = mock.post(TTS_URL.format(voice="v")).mock(
            return_value=httpx.Response(200, content=b"eleven-mp3")
        )
        mock.route(host="testserver").pass_through()
        with _client(_settings(bundle_dir, **eleven)) as client:
            spoken = client.post("/tts/alert", json={"route_key": KEY, "index": 0})
        with _client(_settings(bundle_dir)) as client:
            silent = client.post("/tts/alert", json={"route_key": KEY, "index": 0})

    assert spoken.status_code == 200 and spoken.content == b"eleven-mp3"
    assert eleven_route.call_count == 1
    assert silent.status_code == 503
    assert silent.json()["error"]["code"] == "TTS_UNAVAILABLE"


@pytest.mark.unit
def test_alert_voice_is_a_paid_route() -> None:
    assert is_paid("POST", "/tts/alert")


@pytest.mark.integration
def test_alert_voice_stays_under_the_paid_rate_limit(bundle_dir: Path) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.post(XAI_TTS_URL).mock(return_value=httpx.Response(200, content=b"mp3"))
        mock.route(host="testserver").pass_through()
        with _client(_settings(bundle_dir, paid_rate_limit_per_minute=1)) as client:
            codes = [
                client.post("/tts/alert", json={"route_key": KEY, "index": 0}).status_code
                for _ in range(2)
            ]

    assert codes == [200, 429]
