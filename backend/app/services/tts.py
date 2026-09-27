"""Text-to-speech for already-validated explanations only (VOX-01, NFR-11).

Voices are tried in order (Grok, then ElevenLabs); when none answers, the endpoint tells the
browser to use its own device voice (VOX-04). Each voice caches audio by text and caps paid
calls per day.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from typing import Protocol

import httpx
from cachetools import LRUCache

from app.services.explain.service import DailyBudget

log = logging.getLogger(__name__)
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_64"
XAI_TTS_URL = "https://api.x.ai/v1/tts"
TIMEOUT_S = 6.0
MAX_CHARS = 420
AUDIO_CACHE_SIZE = 256


class Voice(Protocol):
    @property
    def enabled(self) -> bool: ...

    @property
    def label(self) -> str: ...

    async def speak(self, text: str) -> bytes | None: ...


class _CachedVoice:
    """Shared guard rails: length cap, per-text cache, daily budget, errors become None."""

    name = "voice"

    def __init__(self, client: httpx.AsyncClient, daily_budget: int) -> None:
        self._client = client
        self._budget = DailyBudget(daily_budget)
        self._cache: LRUCache[str, bytes] = LRUCache(maxsize=AUDIO_CACHE_SIZE)

    @property
    def enabled(self) -> bool:
        raise NotImplementedError

    @property
    def label(self) -> str:
        """Provider and voice, e.g. "grok:eve": audio caches keyed by it follow voice changes."""
        return f"{self.name}:{self._voice_id}"

    @property
    def _voice_id(self) -> str | None:
        raise NotImplementedError

    async def _request(self, text: str) -> httpx.Response:
        raise NotImplementedError

    async def speak(self, text: str) -> bytes | None:
        """MP3 bytes, or None so the next voice (or the device voice) takes over."""
        if not self.enabled or not text or len(text) > MAX_CHARS:
            return None
        key = hashlib.sha256(text.encode()).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if not self._budget.take():
            return None
        try:
            resp = await self._request(text)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("tts %s failed: %s", self.name, type(exc).__name__)
            return None
        audio = resp.content
        if not audio:
            return None
        self._cache[key] = audio
        return audio


class TtsService(_CachedVoice):
    """ElevenLabs voice."""

    name = "elevenlabs"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
        voice_id: str | None,
        model: str,
        daily_budget: int,
    ) -> None:
        super().__init__(client, daily_budget)
        self._key = api_key
        self._voice = voice_id
        self._model = model

    @property
    def enabled(self) -> bool:
        return bool(self._key and self._voice)

    @property
    def _voice_id(self) -> str | None:
        return self._voice

    async def _request(self, text: str) -> httpx.Response:
        return await self._client.post(
            TTS_URL.format(voice=self._voice),
            json={"text": text, "model_id": self._model},
            headers={"xi-api-key": self._key or "", "Accept": "audio/mpeg"},
            timeout=TIMEOUT_S,
        )


class GrokTtsService(_CachedVoice):
    """xAI Grok voice (MP3)."""

    name = "grok"

    def __init__(
        self, client: httpx.AsyncClient, api_key: str | None, voice_id: str, daily_budget: int
    ) -> None:
        super().__init__(client, daily_budget)
        self._key = api_key
        self._voice = voice_id

    @property
    def enabled(self) -> bool:
        return bool(self._key and self._voice)

    @property
    def _voice_id(self) -> str | None:
        return self._voice

    async def _request(self, text: str) -> httpx.Response:
        return await self._client.post(
            XAI_TTS_URL,
            json={
                "text": text,
                "voice_id": self._voice,
                "language": "en",
                "output_format": {"codec": "mp3"},
            },
            headers={"Authorization": f"Bearer {self._key}", "Accept": "audio/mpeg"},
            timeout=TIMEOUT_S,
        )


class VoiceChain:
    """First voice that answers wins; None means use the device voice."""

    def __init__(self, voices: Sequence[Voice]) -> None:
        self._voices = tuple(voices)

    @property
    def enabled(self) -> bool:
        return any(v.enabled for v in self._voices)

    @property
    def voice_key(self) -> str:
        """The voice that answers first right now ("device" when none is configured)."""
        return next((v.label for v in self._voices if v.enabled), "device")

    async def speak(self, text: str) -> bytes | None:
        for voice in self._voices:
            if not voice.enabled:
                continue
            audio = await voice.speak(text)
            if audio is not None:
                return audio
        return None
