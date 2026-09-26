"""Grok (xAI): explanation provider, provider order, voice chain, and key check."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from app.config import Settings
from app.main import build_providers, create_app
from app.services.explain.evidence import _with_numbers
from app.services.explain.providers import SYSTEM_PROMPT, XAI_CHAT_URL, GrokProvider
from app.services.tts import TTS_URL, XAI_TTS_URL, GrokTtsService, TtsService, VoiceChain
from app.services.weather import FORECAST_URL
from app.tools.check_keys import FAIL, MISSING, OK, check_xai
from fastapi.testclient import TestClient

GOOD = "The PathPro route adds 4.3 min and cuts traffic-risk exposure 49%."
ROUTE = _with_numbers(
    "route",
    {
        "time": "10 PM",
        "conditions": "wet",
        "fastest": {"minutes": 18, "score": 93, "riskiest_streets": []},
        "pathpro": {"minutes": 23, "score": 83, "extra_minutes": 4.3, "less_exposure_percent": 49},
    },
)


def _chat(content: str | None, finish: str = "stop") -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]}
    )


@pytest.mark.unit
@respx.mock
async def test_grok_provider_wire_format() -> None:
    route = respx.post(XAI_CHAT_URL).mock(return_value=_chat(f" {GOOD} "))
    async with httpx.AsyncClient() as client:
        grok = GrokProvider(client, "xai-k", "grok-4.20-0309-non-reasoning")

        assert grok.name == "grok"
        assert await grok.complete(ROUTE, 1.0) == GOOD
    sent = route.calls[0].request
    body = json.loads(sent.content)
    assert sent.headers["Authorization"] == "Bearer xai-k"
    assert body["model"] == "grok-4.20-0309-non-reasoning"
    assert body["max_completion_tokens"] > 0
    assert "max_tokens" not in body
    assert body["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert "Evidence (route)" in body["messages"][1]["content"]


@pytest.mark.unit
@respx.mock
async def test_grok_provider_rejects_truncated_and_empty() -> None:
    respx.post(XAI_CHAT_URL).mock(side_effect=[_chat("The PathPro", "length"), _chat(None)])
    async with httpx.AsyncClient() as client:
        grok = GrokProvider(client, "xai-k", "m")
        with pytest.raises(ValueError, match="incomplete"):
            await grok.complete(ROUTE, 1.0)
        with pytest.raises(ValueError, match="empty"):
            await grok.complete(ROUTE, 1.0)


@pytest.mark.unit
async def test_provider_order_puts_grok_first_only_with_a_key() -> None:
    with_xai = Settings(xai_api_key="xai-k", groq_api_key="g", gemini_api_key="m", _env_file=None)
    without = Settings(groq_api_key="g", gemini_api_key="m", _env_file=None)
    async with httpx.AsyncClient() as client:
        first = [p.name for p in build_providers(with_xai, client)]
        second = [p.name for p in build_providers(without, client)]
        grok_only = [
            p.name for p in build_providers(Settings(xai_api_key="xai-k", _env_file=None), client)
        ]

    assert first == ["grok", "groq", "gemini", "groq-20b"]
    assert second == ["groq", "gemini", "groq-20b"]
    assert grok_only == ["grok"]


@pytest.mark.unit
def test_settings_defaults_for_xai() -> None:
    cfg = Settings(_env_file=None)

    assert cfg.xai_api_key is None
    assert cfg.xai_model == "grok-4.20-0309-non-reasoning"
    assert cfg.xai_image_model == "grok-imagine-image-2.0"
    assert cfg.xai_tts_voice == "eve"
    assert cfg.imagine_daily_budget > 0


@pytest.mark.unit
async def test_grok_tts_disabled_without_key() -> None:
    async with httpx.AsyncClient() as client:
        service = GrokTtsService(client, None, "eve", daily_budget=5)
        assert not service.enabled
        assert await service.speak("hello") is None


@pytest.mark.unit
@respx.mock
async def test_grok_tts_wire_format_cache_and_budget() -> None:
    route = respx.post(XAI_TTS_URL).mock(
        return_value=httpx.Response(200, content=b"mp3", headers={"content-type": "audio/mpeg"})
    )
    async with httpx.AsyncClient() as client:
        service = GrokTtsService(client, "xai-k", "eve", daily_budget=1)

        assert await service.speak("PathPro adds 4 min.") == b"mp3"
        assert await service.speak("PathPro adds 4 min.") == b"mp3"  # cached
        assert await service.speak("Another sentence.") is None  # budget spent
        assert await service.speak("x" * 500) is None  # too long to be an explanation
    assert route.call_count == 1
    sent = route.calls[0].request
    assert sent.headers["Authorization"] == "Bearer xai-k"
    assert json.loads(sent.content) == {
        "text": "PathPro adds 4 min.",
        "voice_id": "eve",
        "language": "en",
        "output_format": {"codec": "mp3"},
    }


@pytest.mark.unit
@respx.mock
async def test_voice_chain_falls_back_from_grok_to_elevenlabs() -> None:
    grok_route = respx.post(XAI_TTS_URL).mock(return_value=httpx.Response(500))
    eleven_route = respx.post(TTS_URL.format(voice="v")).mock(
        return_value=httpx.Response(200, content=b"eleven")
    )
    async with httpx.AsyncClient() as client:
        chain = VoiceChain(
            (GrokTtsService(client, "xai-k", "eve", 5), TtsService(client, "k", "v", "m", 5))
        )

        assert chain.enabled
        assert await chain.speak("Hello there.") == b"eleven"
    assert grok_route.call_count == 1
    assert eleven_route.call_count == 1


@pytest.mark.unit
@respx.mock
async def test_voice_chain_prefers_grok_and_skips_disabled() -> None:
    respx.post(XAI_TTS_URL).mock(return_value=httpx.Response(200, content=b"grok"))
    eleven_route = respx.post(TTS_URL.format(voice="v")).mock(
        return_value=httpx.Response(200, content=b"eleven")
    )
    async with httpx.AsyncClient() as client:
        chain = VoiceChain(
            (GrokTtsService(client, "xai-k", "eve", 5), TtsService(client, "k", "v", "m", 5))
        )
        silent = VoiceChain(
            (GrokTtsService(client, None, "eve", 5), TtsService(client, None, None, "m", 5))
        )

        assert await chain.speak("Hello there.") == b"grok"
        assert not silent.enabled
        assert await silent.speak("Hello there.") is None
    assert eleven_route.call_count == 0


@pytest.mark.unit
@respx.mock
async def test_check_xai_reports_status_without_the_key() -> None:
    respx.get("https://api.x.ai/v1/models").mock(
        side_effect=[httpx.Response(200, json={"data": []}), httpx.Response(401)]
    )
    async with httpx.AsyncClient() as client:
        missing = await check_xai(client, None, "grok-4.20-0309-non-reasoning")
        good = await check_xai(client, "xai-secret", "grok-4.20-0309-non-reasoning")
        bad = await check_xai(client, "xai-secret", "grok-4.20-0309-non-reasoning")

    assert missing[0] == MISSING and "XAI_API_KEY" in missing[1]
    assert good[0] == OK and "grok-4.20-0309-non-reasoning" in good[1]
    assert bad == (FAIL, "HTTP 401")
    assert all("xai-secret" not in note for _, note in (missing, good, bad))


@pytest.mark.integration
def test_tts_endpoint_speaks_only_the_server_explanation_with_grok(bundle_dir: Path) -> None:
    settings = Settings(
        artifacts_dir=bundle_dir, rate_limit_per_minute=1000, xai_api_key="xai-k", _env_file=None
    )
    body = {"kind": "segment", "seg_id": 2, "t": "2026-09-25T22:30", "cond": "dry"}
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.post(XAI_CHAT_URL).mock(return_value=httpx.Response(503))  # explanation: template
        voice = mock.post(XAI_TTS_URL).mock(return_value=httpx.Response(200, content=b"grok-mp3"))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as client:
            spoken = client.post("/tts", json={**body, "text": "say something else"})
            explained = client.post("/explain", json=body).json()["data"]

    assert spoken.status_code == 200
    assert spoken.headers["content-type"] == "audio/mpeg"
    assert spoken.content == b"grok-mp3"
    assert json.loads(voice.calls[0].request.content)["text"] == explained["text"]


@pytest.mark.unit
def test_provider_repr_never_shows_the_api_key() -> None:
    from app.services.explain.providers import GeminiProvider, GrokProvider, GroqProvider

    client = httpx.AsyncClient()
    for cls in (GrokProvider, GroqProvider, GeminiProvider):
        provider = cls(client=client, api_key="xai-supersecret-123", model="m")
        assert "supersecret" not in repr(provider)
        assert "supersecret" not in str(provider)
