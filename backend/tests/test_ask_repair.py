"""Ask PathPro answer coverage: one repair pass, humanized identifiers, a wider docs corpus.

An upstream answer that fails validation gets ONE rewrite request in the same thread (memory
"Readonly", no extra budget, inside the same timeout) before the fixed fallback is used.
Every Backboard call is mocked with respx; the real API is never contacted.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx
import pytest
import respx
from app.config import BACKEND_DIR
from app.services.ask import FALLBACK_TEXT, clean_answer
from app.services.ask_corpus import (
    CORPUS_FILES,
    CORPUS_LABELS,
    CorpusSource,
    corpus_sources,
    load_allowed_numbers,
)
from app.services.ask_rewrite import humanize_identifiers, repair_request
from app.services.backboard import Backboard
from app.services.explain.validator import ask_validation_errors
from app.tools.setup_backboard import SYSTEM_PROMPT, run_setup

from tests.test_ask import (
    ASSISTANT,
    CLIENT,
    GOOD,
    MESSAGES_URL,
    THREAD,
    THREADS_URL,
    TOKENS,
    _body,
    _reply,
    _service,
)
from tests.test_ask_memory import CLONE, CLONE_THREADS_URL, MEMORY
from tests.test_backboard_setup import KEY, FakeBackboard, _corpus, _no_sleep

QUESTION = "Is it safe to walk on Peachtree Street at night?"
UNSAFE_ANSWER = (
    "Yes, PathPro says Peachtree Street is safe at night: its traffic risk is lower than most "
    "streets."
)
REWRITE = "PathPro rates Peachtree Street as lower-risk at night compared with most streets."
STILL_BAD = "Peachtree Street is one of the safest streets on PathPro's map."


def _repair_body(messages: respx.Route) -> dict[str, object]:
    return _body(messages, 1)


# --- repair pass ------------------------------------------------------------------------------


@pytest.mark.unit
async def test_banned_word_answer_is_repaired_in_the_same_thread() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(
            side_effect=[_reply(UNSAFE_ANSWER), _reply(REWRITE)]
        )
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert answer.source == "backboard"
    assert answer.text == REWRITE
    assert answer.thread_id == TOKENS.issue(THREAD, ASSISTANT)
    assert messages.call_count == 2
    repair = _repair_body(messages)
    assert repair["thread_id"] == THREAD
    assert repair["assistant_id"] == ASSISTANT
    assert repair["memory"] == "Readonly"
    content = str(repair["content"])
    assert "safe" in content  # names the banned word it found
    assert "lower-risk" in content and "higher traffic risk" in content


@pytest.mark.unit
async def test_new_thread_repair_reuses_the_thread_it_created() -> None:
    with respx.mock() as mock:
        threads = mock.post(THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(
            side_effect=[_reply(UNSAFE_ANSWER), _reply(REWRITE)]
        )
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(QUESTION, None, client=CLIENT)

    assert answer.source == "backboard"
    assert threads.call_count == 1  # the repair never creates a second thread
    assert _repair_body(messages)["thread_id"] == THREAD


@pytest.mark.unit
async def test_failed_repair_falls_back_and_keeps_the_thread() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(
            side_effect=[_reply(UNSAFE_ANSWER), _reply(STILL_BAD)]
        )
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert messages.call_count == 2  # exactly one repair, never a loop
    assert answer.source == "fallback"
    assert answer.text == FALLBACK_TEXT
    assert answer.thread_id == TOKENS.issue(THREAD, ASSISTANT)


@pytest.mark.unit
async def test_repair_upstream_error_falls_back_and_keeps_the_thread() -> None:
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(
            side_effect=[_reply(UNSAFE_ANSWER), httpx.Response(500, json={"detail": "boom"})]
        )
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert answer.source == "fallback"
    assert answer.thread_id == TOKENS.issue(THREAD, ASSISTANT)


@pytest.mark.unit
async def test_repair_on_a_memory_clone_is_readonly() -> None:
    with respx.mock() as mock:
        mock.post(CLONE_THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(
            side_effect=[_reply(UNSAFE_ANSWER), _reply(REWRITE)]
        )
        async with httpx.AsyncClient() as client:
            answer = await _service(client, memory_tokens=MEMORY).ask(
                QUESTION, None, client=CLIENT, memory_token=MEMORY.issue(CLONE)
            )

    assert answer.source == "backboard" and answer.memory == "on"
    assert _body(messages, 0)["memory"] == "Auto"  # the question itself may write memory
    repair = _repair_body(messages)
    assert repair["assistant_id"] == CLONE
    assert repair["memory"] == "Readonly"  # the rewrite request never does
    assert answer.thread_id == TOKENS.issue(THREAD, CLONE)


@pytest.mark.unit
async def test_repair_consumes_no_extra_budget() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(
            side_effect=[_reply(UNSAFE_ANSWER), _reply(REWRITE), _reply(GOOD)]
        )
        async with httpx.AsyncClient() as client:
            service = _service(client, daily_budget=2, per_client_daily=2)
            first = await service.ask(QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT)
            second = await service.ask(
                "How was the model tested?", TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert first.source == "backboard" and second.source == "backboard"
    assert messages.call_count == 3


@pytest.mark.unit
async def test_valid_answers_are_never_repaired() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply(GOOD))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                "How was the model tested?", TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert answer.source == "backboard"
    assert messages.call_count == 1


@pytest.mark.unit
async def test_repair_stays_inside_the_ask_timeout() -> None:
    async def slow_rewrite(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return _reply(REWRITE)

    seen: list[int] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        if len(seen) == 1:
            return _reply(UNSAFE_ANSWER)
        return await slow_rewrite(request)

    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(side_effect=respond)
        async with httpx.AsyncClient() as client:
            started = time.monotonic()
            answer = await _service(client, timeout_s=1.5).ask(
                QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )
            elapsed = time.monotonic() - started

    assert messages.call_count == 2
    assert answer.source == "fallback"
    assert answer.thread_id == TOKENS.issue(THREAD, ASSISTANT)
    assert elapsed < 2.5  # the whole ask, repair included, keeps the original timeout


@pytest.mark.unit
async def test_no_repair_when_too_little_time_is_left(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.ask.MIN_REPAIR_S", 60.0)
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply(UNSAFE_ANSWER))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert messages.call_count == 1
    assert answer.source == "fallback"


@pytest.mark.unit
async def test_repair_logs_only_error_categories(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(side_effect=[_reply(UNSAFE_ANSWER), _reply(STILL_BAD)])
        async with httpx.AsyncClient() as client:
            await _service(client).ask(QUESTION, TOKENS.issue(THREAD, ASSISTANT), client=CLIENT)

    assert "banned_phrase" in caplog.text
    for secret in (UNSAFE_ANSWER, STILL_BAD, "Peachtree", "safest", QUESTION):
        assert secret not in caplog.text


# --- repair instructions ----------------------------------------------------------------------


@pytest.mark.unit
def test_repair_request_lists_the_banned_words_found() -> None:
    text = "PathPro's route is safe, even safer than the fastest, and never dangerous."
    request = repair_request(text, ["banned_phrase"])

    for word in ("safe", "safer", "dangerous"):
        assert word in request, word
    assert "lower-risk" in request and "higher traffic risk" in request


@pytest.mark.unit
@pytest.mark.parametrize(
    ("errors", "text", "expected"),
    [
        (["internal_term"], "PathPro's lit_and_busy option", ("lit_and_busy", "Well-lit & busier")),
        (["too_long"], "PathPro " * 200, ("120 words",)),
        (["unknown_number:97.5"], "PathPro is 97.5% right.", ("97.5", "Context block")),
        (["link"], "See example.com for PathPro.", ("pathpro.tech",)),
        (["off_topic"], "Paris is lovely.", ("about PathPro",)),
        (
            ["crime_framing"],
            "PathPro avoids high-crime areas.",
            ("informational only", "never used for routing"),
        ),
    ],
)
def test_repair_request_explains_each_error(
    errors: list[str], text: str, expected: tuple[str, ...]
) -> None:
    request = repair_request(text, errors)

    for phrase in expected:
        assert phrase in request, phrase
    assert request.count("\n- ") == len(errors)  # one instruction per error category


@pytest.mark.unit
def test_repair_request_merges_repeated_number_errors() -> None:
    request = repair_request(
        "PathPro: 97.5 and 3000.", ["unknown_number:97.5", "unknown_number:3000"]
    )

    assert "97.5" in request and "3000" in request
    assert request.count("\n- ") == 1


# --- humanized identifiers --------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PathPro's lit_and_busy option", "PathPro's Well-lit & busier option"),
        ("the lower_traffic_risk default", "the lower traffic risk default"),
        ("Pick `lit_and_busy` after dark", "Pick Well-lit & busier after dark"),
        ("a blue_light near campus", "a blue-light emergency phone near campus"),
        ("a sidewalk_blocked report", "a sidewalk blocked report"),
        (
            "the extra_minutes and less_exposure_percent",
            "the extra minutes and less exposure percent",
        ),
        (
            "See model_card.md and docs/guide/user_guide.md",
            "See model_card.md and docs/guide/user_guide.md",
        ),
    ],
)
def test_identifiers_become_app_labels(raw: str, expected: str) -> None:
    assert humanize_identifiers(raw) == expected


@pytest.mark.unit
def test_clean_answer_humanizes_so_the_label_passes_validation() -> None:
    text = clean_answer("PathPro's lit_and_busy routing preference favors well-lit streets.")

    assert text == "PathPro's Well-lit & busier routing preference favors well-lit streets."
    assert ask_validation_errors(text, frozenset()) == []


@pytest.mark.unit
async def test_identifier_answer_is_shown_without_a_repair() -> None:
    raw = "PathPro's lit_and_busy route preference favors well-lit, busier streets after dark."
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply(raw))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                "How does the well-lit option work?", TOKENS.issue(THREAD, ASSISTANT), client=CLIENT
            )

    assert answer.source == "backboard"
    assert "Well-lit & busier" in answer.text and "lit_and_busy" not in answer.text
    assert messages.call_count == 1


# --- corpus -----------------------------------------------------------------------------------


@pytest.mark.unit
def test_corpus_includes_the_user_guide_and_readme() -> None:
    assert "docs/guide/user_guide.md" in CORPUS_FILES
    assert "README.md" in CORPUS_FILES
    assert CORPUS_LABELS["docs/guide/user_guide.md"] == "User guide"
    assert CORPUS_LABELS["README.md"] == "README"
    root = BACKEND_DIR.parent
    assert (root / "docs/guide/user_guide.md").is_file()
    assert (root / "README.md").is_file()


@pytest.mark.unit
def test_allowed_numbers_include_the_guide_and_readme() -> None:
    numbers = load_allowed_numbers(BACKEND_DIR.parent)

    assert 93.0 in numbers  # the route card's "93 risk" example, only in the user guide
    assert 4.2 in numbers  # "+4.2 min" in the README's headline example


@pytest.mark.unit
def test_new_corpus_files_are_cited_as_sources() -> None:
    raw = "Tap the agent 【1:0†user_guide.md】 as the README says 【2:1†README.md】."

    assert corpus_sources(raw) == (
        CorpusSource(
            "User guide",
            "https://github.com/ShaikNagurShareef/PathPro/blob/main/docs/guide/user_guide.md",
        ),
        CorpusSource("README", "https://github.com/ShaikNagurShareef/PathPro/blob/main/README.md"),
    )


@pytest.mark.unit
@pytest.mark.parametrize("name", ["user_guide.md", "README.md", "docs/guide/user_guide.md"])
def test_validator_allows_naming_the_new_corpus_files(name: str) -> None:
    text = f"The PathPro {name} explains how to plan a route."

    assert ask_validation_errors(text, frozenset()) == []


# --- system prompt ----------------------------------------------------------------------------


@pytest.mark.unit
def test_system_prompt_covers_how_to_predictions_and_wording() -> None:
    prompt = SYSTEM_PROMPT.lower()

    for rule in (
        "user guide",
        "how-to",
        "factor by factor",
        "extra minutes",
        "avoided",
        "if asked whether something is safe",
        "code identifiers",
        "well-lit & busier",
    ):
        assert rule in prompt, rule
    # the existing rules stay
    for rule in ("don't know", "120 words", "never used for routing", "never rank"):
        assert rule in prompt, rule


@pytest.mark.unit
async def test_setup_uploads_the_new_corpus_files(tmp_path: Path) -> None:
    _corpus(tmp_path, ("docs/guide/user_guide.md", "README.md"))
    with respx.mock() as mock:
        fake = FakeBackboard(mock)
        async with httpx.AsyncClient() as client:
            result = await run_setup(Backboard(client, KEY), tmp_path, sleep=_no_sleep)

    assert fake.uploads == ["user_guide.md", "README.md"]
    assert result.documents == {"user_guide.md": "indexed", "README.md": "indexed"}
