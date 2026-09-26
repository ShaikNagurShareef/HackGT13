"""Explanation chain: cache -> Groq -> Gemini -> template, all validated (GEN-01..04, EC-40/41)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

import httpx
from cachetools import LRUCache

from app.services.explain import template
from app.services.explain.evidence import Evidence
from app.services.explain.providers import Provider
from app.services.explain.validator import validation_errors

log = logging.getLogger(__name__)
CACHE_SIZE = 4096


@dataclass(frozen=True)
class Explanation:
    text: str
    source: str  # groq | gemini | template | cache


class ExplainService:
    def __init__(
        self,
        providers: Sequence[Provider],
        total_budget_s: float = 3.0,
        first_budget_s: float = 1.6,
    ) -> None:
        self._providers = tuple(providers)
        self._total = total_budget_s
        self._first = first_budget_s
        self._cache: LRUCache[str, Explanation] = LRUCache(maxsize=CACHE_SIZE)

    async def explain(self, key: str, evidence: Evidence) -> Explanation:
        cached = self._cache.get(key)
        if cached is not None:
            return Explanation(cached.text, "cache")
        result = await self._generate(evidence)
        self._cache[key] = result
        return result

    async def _generate(self, evidence: Evidence) -> Explanation:
        deadline = time.monotonic() + self._total
        for i, provider in enumerate(self._providers):
            remaining = deadline - time.monotonic()
            if remaining <= 0.2:
                break
            budget = (
                min(remaining, self._first) if i == 0 and len(self._providers) > 1 else remaining
            )
            text = await self._try(provider, evidence, budget)
            if text is not None:
                return Explanation(text, provider.name)
        return Explanation(template.render(evidence), "template")

    async def _try(self, provider: Provider, evidence: Evidence, budget: float) -> str | None:
        try:
            text = await asyncio.wait_for(provider.complete(evidence, budget), timeout=budget)
        except (TimeoutError, httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            log.warning("explain provider %s failed: %s", provider.name, type(exc).__name__)
            return None
        errors = validation_errors(text, evidence)
        if errors:
            log.warning("explain provider %s output rejected: %s", provider.name, errors[:3])
            return None
        return text
