"""Grounded explanations: validator, templates, provider chain, cache (GEN-01..04)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import pytest
import respx
from app.services.explain import template
from app.services.explain.evidence import Evidence, _with_numbers
from app.services.explain.providers import GEMINI_URL, GROQ_URL, GeminiProvider, GroqProvider
from app.services.explain.service import ExplainService
from app.services.explain.validator import validation_errors

ROUTE = _with_numbers(
    "route",
    {
        "time": "10 PM",
        "conditions": "wet",
        "fastest": {"minutes": 18, "score": 93, "riskiest_streets": ["10th Street Northwest"]},
        "pathpulse": {
            "minutes": 23,
            "score": 83,
            "extra_minutes": 4.3,
            "less_exposure_percent": 49,
            "avoids": ["Peachtree Place Northwest"],
        },
        "unavoidable": ["Fifth Street Northwest"],
    },
)
SEGMENT = _with_numbers(
    "segment",
    {
        "street": "I-85 Access Road",
        "score": 96,
        "band": "High",
        "time": "10 PM",
        "conditions": "wet",
        "confidence": "limited",
        "raises_risk": [{"factor": "Vehicle crashes on this street", "points": 26}],
        "lowers_risk": [],
        "history": {"crashes": 107, "pedestrian_crashes": 1, "period": "2020-2024"},
    },
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("This route is totally safe.", "banned_phrase"),
        ("Crime is higher here.", "banned_phrase"),
        ("It cuts exposure 80%.", "unknown_number:80"),
        ("At 9 PM the risk rises.", "unknown_time:9 PM"),
        ("One. Two. Three. Four.", "too_many_sentences"),
        ("", "empty"),
    ],
)
def test_validator_rejects(text: str, error: str) -> None:
    assert error in validation_errors(text, ROUTE)


@pytest.mark.unit
def test_validator_accepts_grounded_text_with_street_numbers() -> None:
    text = (
        "At 10 PM in wet conditions the PathPulse route adds 4.3 min but cuts exposure 49% "
        "by skipping Peachtree Place Northwest; 10th Street Northwest scores 93."
    )

    assert validation_errors(text, ROUTE) == []


@pytest.mark.unit
@pytest.mark.parametrize("evidence", [ROUTE, SEGMENT])
def test_templates_always_validate(evidence: Evidence) -> None:
    text = template.render(evidence)

    assert validation_errors(text, evidence) == []
    assert "safe" not in text.lower()


@pytest.mark.unit
def test_route_template_without_alternative() -> None:
    ev = _with_numbers(
        "route",
        {
            "time": "1 PM",
            "conditions": "dry",
            "fastest_is_lower_risk": True,
            "fastest": {"minutes": 8, "score": 50, "riskiest_streets": []},
        },
    )

    assert template.render(ev) == "The fastest route is already the lower-risk option."


@dataclass
class FakeProvider:
    name: str
    reply: str | None = None
    delay: float = 0.0
    fail: bool = False
    calls: int = 0

    async def complete(self, evidence: Evidence, timeout_s: float) -> str:
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.fail:
            raise httpx.ConnectError("down")
        assert self.reply is not None
        return self.reply


GOOD = "The PathPulse route adds 4.3 min and cuts traffic-risk exposure 49%."


@pytest.mark.unit
async def test_first_valid_provider_wins_and_is_cached() -> None:
    groq = FakeProvider("groq", reply=GOOD)
    service = ExplainService([groq, FakeProvider("gemini", reply=GOOD)])

    first = await service.explain("k1", ROUTE)
    second = await service.explain("k1", ROUTE)

    assert (first.source, second.source) == ("groq", "cache")
    assert second.text == GOOD
    assert groq.calls == 1


@pytest.mark.unit
async def test_invalid_output_falls_through_to_next_provider() -> None:
    service = ExplainService(
        [
            FakeProvider("groq", reply="Totally safe, 99% fewer crashes."),
            FakeProvider("gemini", reply=GOOD),
        ]
    )

    result = await service.explain("k2", ROUTE)

    assert result.source == "gemini"


@pytest.mark.unit
async def test_timeouts_and_errors_fall_back_to_template_within_budget() -> None:
    service = ExplainService(
        [FakeProvider("groq", reply=GOOD, delay=2.0), FakeProvider("gemini", fail=True)],
        total_budget_s=0.6,
        first_budget_s=0.3,
    )

    result = await service.explain("k3", ROUTE)

    assert result.source == "template"
    assert validation_errors(result.text, ROUTE) == []


@pytest.mark.unit
async def test_no_providers_uses_template() -> None:
    result = await ExplainService([]).explain("k4", SEGMENT)

    assert result.source == "template"
    assert "leans on street characteristics" in result.text


@pytest.mark.unit
@respx.mock
async def test_groq_and_gemini_wire_formats() -> None:
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": f" {GOOD} "}}]}
        )
    )
    respx.post(GEMINI_URL.format(model="gemini-3.8-flash")).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": GOOD}]}}]}
        )
    )
    async with httpx.AsyncClient() as client:
        groq = GroqProvider(client, "k", "openai/gpt-oss-120b")
        gemini = GeminiProvider(client, "k", "gemini-3.8-flash")

        assert await groq.complete(ROUTE, 1.0) == GOOD
        assert await gemini.complete(ROUTE, 1.0) == GOOD
    sent = respx.calls[0].request
    assert sent.headers["Authorization"] == "Bearer k"
    assert b"Evidence (route)" in sent.content


@pytest.mark.unit
async def test_template_fallbacks_are_not_cached_and_budget_caps_calls() -> None:
    flaky = FakeProvider("groq", fail=True)
    service = ExplainService([flaky], daily_budget=1)

    first = await service.explain("k5", ROUTE)
    second = await service.explain("k5", ROUTE)

    assert (first.source, second.source) == ("template", "template")
    assert flaky.calls == 1  # second call skipped providers: daily budget spent


@pytest.mark.unit
async def test_concurrent_requests_share_one_provider_call() -> None:
    groq = FakeProvider("groq", reply=GOOD, delay=0.05)
    service = ExplainService([groq])

    results = await asyncio.gather(*(service.explain("k6", ROUTE) for _ in range(5)))

    assert groq.calls == 1
    assert {r.text for r in results} == {GOOD}


@pytest.mark.unit
@respx.mock
async def test_truncated_or_empty_completions_are_rejected() -> None:
    respx.post(GROQ_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "choices": [
                        {"finish_reason": "length", "message": {"content": "The PathPulse"}}
                    ]
                },
            ),
            httpx.Response(
                200, json={"choices": [{"finish_reason": "stop", "message": {"content": None}}]}
            ),
        ]
    )
    async with httpx.AsyncClient() as client:
        groq = GroqProvider(client, "k", "openai/gpt-oss-120b")
        with pytest.raises(ValueError, match="incomplete"):
            await groq.complete(ROUTE, 1.0)
        with pytest.raises(ValueError, match="empty"):
            await groq.complete(ROUTE, 1.0)
