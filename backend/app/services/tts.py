"""ElevenLabs text-to-speech for already-validated explanations only (VOX-01, NFR-11)."""

from __future__ import annotations

import hashlib
import logging

import httpx
from cachetools import LRUCache

from app.services.explain.service import DailyBudget

log = logging.getLogger(__name__)
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_64"
TIMEOUT_S = 6.0
MAX_CHARS = 420


class TtsService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
        voice_id: str | None,
        model: str,
        daily_budget: int,
    ) -> None:
        self._client = client
        self._key = api_key
        self._voice = voice_id
        self._model = model
        self._budget = DailyBudget(daily_budget)
        self._cache: LRUCache[str, bytes] = LRUCache(maxsize=256)

    @property
    def enabled(self) -> bool:
        return bool(self._key and self._voice)

    async def speak(self, text: str) -> bytes | None:
        """MP3 bytes, or None so the browser falls back to its own speech (VOX-04)."""
        if not self.enabled or not text or len(text) > MAX_CHARS:
            return None
        key = hashlib.sha256(text.encode()).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if not self._budget.take():
            return None
        try:
            resp = await self._client.post(
                TTS_URL.format(voice=self._voice),
                json={"text": text, "model_id": self._model},
                headers={"xi-api-key": self._key or "", "Accept": "audio/mpeg"},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("tts failed: %s", type(exc).__name__)
            return None
        audio = resp.content
        self._cache[key] = audio
        return audio
