"""Voice: only server-produced explanations are spoken; graceful fallback."""

from __future__ import annotations

import httpx
import pytest
import respx
from app.services.tts import TTS_URL, TtsService


@pytest.mark.unit
async def test_disabled_without_key_returns_none() -> None:
    async with httpx.AsyncClient() as client:
        service = TtsService(client, None, None, "m", 10)
        assert not service.enabled
        assert await service.speak("hello") is None


@pytest.mark.unit
@respx.mock
async def test_speaks_caches_and_respects_budget() -> None:
    route = respx.post(TTS_URL.format(voice="v")).mock(
        return_value=httpx.Response(200, content=b"mp3")
    )
    async with httpx.AsyncClient() as client:
        service = TtsService(client, "k", "v", "eleven_flash_v2_5", daily_budget=1)

        assert await service.speak("PathPro adds 4 min.") == b"mp3"
        assert await service.speak("PathPro adds 4 min.") == b"mp3"  # cached
        assert await service.speak("Another sentence.") is None  # budget spent
    assert route.call_count == 1
    assert route.calls[0].request.headers["xi-api-key"] == "k"


@pytest.mark.unit
@respx.mock
async def test_provider_error_falls_back() -> None:
    respx.post(TTS_URL.format(voice="v")).mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        service = TtsService(client, "k", "v", "m", 5)
        assert await service.speak("text") is None
        assert await service.speak("x" * 500) is None
