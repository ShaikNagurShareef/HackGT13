"""LLM providers behind one interface: Groq (OpenAI-compatible) and Gemini REST."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.services.explain.evidence import Evidence

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """You explain pedestrian TRAFFIC risk scores for a walking map of Atlanta.
Rules:
- Use ONLY the facts in the JSON evidence. Every number you write must appear in it.
- 1 to 3 short sentences, plain English, calm tone.
- Say "traffic risk", "lower-risk", "historical crashes". Never say safe, safest, guaranteed,
  crime, or dangerous area/neighborhood. Never mention people, neighborhoods, or demographics.
- Name at most three factors or streets and at most one concrete action.
- Do not invent scores, times, or percentages. Output only the explanation text."""


class Provider(Protocol):
    name: str

    async def complete(self, evidence: Evidence, timeout_s: float) -> str: ...


def user_message(evidence: Evidence) -> str:
    return f"Evidence ({evidence.kind}):\n{json.dumps(evidence.payload, ensure_ascii=False)}"


@dataclass(frozen=True)
class GroqProvider:
    client: httpx.AsyncClient
    api_key: str
    model: str
    name: str = "groq"

    async def complete(self, evidence: Evidence, timeout_s: float) -> str:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 160,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message(evidence)},
            ],
        }
        resp = await self.client.post(
            GROQ_URL,
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"]).strip()


@dataclass(frozen=True)
class GeminiProvider:
    client: httpx.AsyncClient
    api_key: str
    model: str
    name: str = "gemini"

    async def complete(self, evidence: Evidence, timeout_s: float) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_message(evidence)}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 160},
        }
        resp = await self.client.post(
            GEMINI_URL.format(model=self.model),
            json=body,
            headers={"x-goog-api-key": self.api_key},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(str(p.get("text", "")) for p in parts).strip()
