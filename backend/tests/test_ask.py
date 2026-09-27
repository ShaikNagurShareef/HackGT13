"""Ask PathPro: Backboard-backed Q&A about PathPro's own docs, validated before it is shown.

Every Backboard call is mocked with respx; the real API is never contacted.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from app.api.envelope import AppError
from app.config import BACKEND_DIR, Settings
from app.main import create_app
from app.middleware import is_paid
from app.services.ask import (
    ASK_NOTE,
    FALLBACK_TEXT,
    AskService,
    clean_question,
    parse_thread_id,
)
from app.services.ask_corpus import allowed_numbers, load_allowed_numbers
from app.services.backboard import BACKBOARD_API, Backboard
from app.services.explain.validator import ask_validation_errors
from app.services.weather import FORECAST_URL
from app.tools.check_keys import FAIL, MISSING, OK, check_backboard
from fastapi.testclient import TestClient

KEY = "bb-test-key-do-not-print"
ASSISTANT = "11111111-1111-4111-8111-111111111111"
THREAD = "22222222-2222-4222-8222-222222222222"
OTHER_THREAD = "33333333-3333-4333-8333-333333333333"
CORPUS = (
    "On the 2024 holdout the top 10% of street length held 74.3% of pedestrian crashes, "
    "versus 53.8% for the High Injury Network. metrics: 0.412. Routes cut exposure 54%. "
    "Crash data 2020-2024; 1,250 segments."
)
ALLOWED = allowed_numbers([CORPUS])
GOOD = (
    "PathPro was tested on held-out 2024 crashes: the top 10% of street length held 74.3% "
    "of pedestrian crashes, versus 53.8% for the High Injury Network."
)
THREADS_URL = f"{BACKBOARD_API}/assistants/{ASSISTANT}/threads"
MESSAGES_URL = f"{BACKBOARD_API}/threads/messages"


def _reply(
    content: str | None = GOOD, thread: str = THREAD, status: str = "COMPLETED"
) -> httpx.Response:
    return httpx.Response(
        200, json={"content": content, "thread_id": thread, "status": status, "role": "assistant"}
    )


def _service(client: httpx.AsyncClient, **over: object) -> AskService:
    kw: dict[str, object] = {
        "llm_provider": "google",
        "model_name": "gemini-3.1-flash-lite",
        "daily_budget": 300,
    }
    kw.update(over)
    return AskService(Backboard(client, KEY), ASSISTANT, ALLOWED, **kw)  # type: ignore[arg-type]


def _body(route: respx.Route, i: int = -1) -> dict[str, object]:
    call = route.calls[i]
    return json.loads(call.request.content)  # type: ignore[no-any-return]


# --- question and thread id validation -------------------------------------------------------


@pytest.mark.unit
def test_question_is_stripped_and_bounded() -> None:
    assert clean_question("  How was the model tested?  ") == "How was the model tested?"
    for bad in ("", "  hi ", "x" * 301, "why\x00 crime?", "tab\tsneak", "line\nbreak here"):
        with pytest.raises(AppError) as err:
            clean_question(bad)
        assert err.value.code == "BAD_QUESTION" and err.value.status == 422


@pytest.mark.unit
def test_question_length_edges() -> None:
    assert clean_question("abc") == "abc"
    assert len(clean_question("y" * 300)) == 300


@pytest.mark.unit
def test_thread_id_must_be_a_uuid() -> None:
    assert parse_thread_id(None) is None
    assert parse_thread_id(THREAD.upper()) == THREAD
    for bad in ("", "not-a-uuid", "../../assistants", THREAD + "x", "1" * 32 + "/x"):
        with pytest.raises(AppError) as err:
            parse_thread_id(bad)
        assert err.value.code == "BAD_THREAD" and err.value.status == 422


# --- answer validation -----------------------------------------------------------------------


@pytest.mark.unit
def test_allowed_numbers_tolerate_formatting() -> None:
    for value in (74.3, 53.8, 2024.0, 10.0, 1250.0, 41.2, 54.0):
        assert value in ALLOWED, value
    assert ask_validation_errors(GOOD, ALLOWED) == []
    assert ask_validation_errors("It held 74.3 percent; about 54% less exposure.", ALLOWED) == []
    assert ask_validation_errors("The data covers 1,250 segments.", ALLOWED) == []


@pytest.mark.unit
def test_validator_rejects_invented_numbers() -> None:
    errors = ask_validation_errors("The model is 97.5% accurate on 3,000 streets.", ALLOWED)

    assert "unknown_number:97.5" in errors
    assert "unknown_number:3000" in errors


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "The lower-risk route is the safest way to walk.",
        "PathPro keeps you safe on every walk.",
        "Results are guaranteed.",
        "Some streets are in a dangerous area of town.",
        "That is a bad area after dark.",
    ],
)
def test_validator_rejects_banned_words(text: str) -> None:
    assert "banned_phrase" in ask_validation_errors(text, ALLOWED)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "PathPro avoids high-crime neighborhoods.",
        "Routes steer around crime hotspots.",
        "Crime reports are used to pick the route.",
        "The traffic-risk score includes crime.",
    ],
)
def test_validator_rejects_crime_framing(text: str) -> None:
    assert "crime_framing" in ask_validation_errors(text, ALLOWED)


@pytest.mark.unit
def test_validator_allows_informational_crime_wording() -> None:
    text = (
        "Reported crimes against persons are shown for information only, with a fairness note. "
        "Crime data is never used for routing or in the traffic-risk model."
    )

    assert ask_validation_errors(text, ALLOWED) == []


@pytest.mark.unit
def test_validator_rejects_long_or_empty_answers() -> None:
    assert ask_validation_errors("   ", ALLOWED) == ["empty"]
    assert "too_long" in ask_validation_errors("word " * 200, ALLOWED)


@pytest.mark.unit
def test_corpus_numbers_come_from_the_repo_docs() -> None:
    numbers = load_allowed_numbers(BACKEND_DIR.parent)

    assert {74.3, 53.8} <= numbers


@pytest.mark.unit
def test_corpus_missing_files_fail_closed(tmp_path: Path) -> None:
    assert load_allowed_numbers(tmp_path) == frozenset()


# --- service ---------------------------------------------------------------------------------


@pytest.mark.unit
async def test_ask_new_thread_uses_readonly_memory() -> None:
    with respx.mock(assert_all_called=True) as mock:
        threads = mock.post(THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("How was the model tested?", None)

    assert answer.source == "backboard"
    assert answer.text == GOOD
    assert answer.thread_id == THREAD
    assert answer.sources_note == ASK_NOTE
    assert json.loads(threads.calls[0].request.content) == {}
    body = _body(messages)
    assert body["memory"] == "Readonly"
    assert body["thread_id"] == THREAD
    assert body["assistant_id"] == ASSISTANT
    assert body["content"] == "How was the model tested?"
    assert body["stream"] is False
    assert body["send_to_llm"] == "true"
    assert body["llm_provider"] == "google"
    assert body["model_name"] == "gemini-3.1-flash-lite"
    for call in (*threads.calls, *messages.calls):
        assert call.request.headers["X-API-Key"] == KEY


@pytest.mark.unit
async def test_ask_existing_thread_skips_thread_creation() -> None:
    with respx.mock(assert_all_called=False) as mock:
        threads = mock.post(THREADS_URL).mock(return_value=httpx.Response(200, json={}))
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply(thread=OTHER_THREAD))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("Tell me more", OTHER_THREAD)

    assert not threads.called
    assert _body(messages)["thread_id"] == OTHER_THREAD
    assert _body(messages)["memory"] == "Readonly"
    assert answer.thread_id == OTHER_THREAD


@pytest.mark.unit
async def test_empty_model_uses_backboard_default() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            await _service(client, model_name="").ask("How was the model tested?", THREAD)

    body = _body(messages)
    assert "model_name" not in body and "llm_provider" not in body


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "PathPro is 97.5% accurate.",  # invented number
        "The lower-risk route is the safest way home.",  # banned word
        "PathPro avoids high-crime neighborhoods.",  # crime framing
    ],
)
async def test_rejected_answers_become_the_fallback(content: str) -> None:
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=_reply(content))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("How was the model tested?", THREAD)

    assert answer.source == "fallback"
    assert answer.text == FALLBACK_TEXT
    assert content not in answer.text
    assert answer.thread_id == THREAD  # the thread still works; only this answer was withheld


@pytest.mark.unit
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"detail": "boom"}),
        httpx.Response(404, json={"detail": "thread not found"}),
        httpx.Response(200, json={"content": None, "thread_id": THREAD, "status": "FAILED"}),
        httpx.Response(200, json={"content": GOOD, "thread_id": THREAD, "status": "IN_PROGRESS"}),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, text="<html>gateway</html>"),
    ],
)
async def test_upstream_failures_become_the_fallback(response: httpx.Response) -> None:
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=response)
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("How was the model tested?", THREAD)

    assert answer.source == "fallback"
    assert answer.text == FALLBACK_TEXT
    assert answer.thread_id is None  # the client starts a fresh thread next time


@pytest.mark.unit
async def test_timeout_becomes_the_fallback_and_logs_only_type_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(side_effect=httpx.ReadTimeout(f"secret {KEY}"))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("How was the model tested?", THREAD)

    assert answer.source == "fallback"
    assert "ReadTimeout" in caplog.text
    assert KEY not in caplog.text
    assert "How was the model tested" not in caplog.text


@pytest.mark.unit
async def test_rejected_answer_text_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=_reply("It is 97.5% guaranteed."))
        async with httpx.AsyncClient() as client:
            await _service(client).ask("How was the model tested?", THREAD)

    assert "97.5% guaranteed" not in caplog.text


@pytest.mark.unit
async def test_daily_budget_caps_backboard_calls() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            service = _service(client, daily_budget=1)
            first = await service.ask("How was the model tested?", THREAD)
            second = await service.ask("How was the model tested?", THREAD)

    assert first.source == "backboard"
    assert second.source == "fallback"
    assert messages.call_count == 1


@pytest.mark.unit
async def test_citation_markers_are_stripped() -> None:
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=_reply(f"{GOOD}【4:0†model_card.md】 [2]"))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("How was the model tested?", THREAD)

    assert answer.source == "backboard"
    assert answer.text == GOOD


@pytest.mark.unit
async def test_service_without_key_is_disabled() -> None:
    service = AskService(None, ASSISTANT, ALLOWED, daily_budget=10)
    assert not service.enabled
    with pytest.raises(AppError) as err:
        await service.ask("How was the model tested?", None)
    assert err.value.code == "ASK_UNAVAILABLE" and err.value.status == 503


# --- API -------------------------------------------------------------------------------------


def _client(bundle_dir: Path, **over: object) -> Iterator[tuple[TestClient, respx.MockRouter]]:
    settings = Settings(
        artifacts_dir=bundle_dir,
        rate_limit_per_minute=1000,
        paid_rate_limit_per_minute=1000,
        _env_file=None,
        **over,  # type: ignore[arg-type]
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as client:
            yield client, mock


@pytest.fixture
def ask_api(bundle_dir: Path) -> Iterator[tuple[TestClient, respx.MockRouter]]:
    yield from _client(bundle_dir, backboard_api_key=KEY, backboard_assistant_id=ASSISTANT)


@pytest.mark.integration
def test_post_ask_returns_the_envelope(ask_api: tuple[TestClient, respx.MockRouter]) -> None:
    client, mock = ask_api
    mock.post(THREADS_URL).mock(return_value=httpx.Response(200, json={"thread_id": THREAD}))
    messages = mock.post(MESSAGES_URL).mock(return_value=_reply())

    resp = client.post("/ask", json={"question": "How was the model tested?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == {
        "answer": GOOD,
        "thread_id": THREAD,
        "source": "backboard",
        "note": "Answered from PathPro's model card and docs · powered by Backboard",
    }
    assert _body(messages)["memory"] == "Readonly"


@pytest.mark.integration
def test_post_ask_fallback_is_still_success(ask_api: tuple[TestClient, respx.MockRouter]) -> None:
    client, mock = ask_api
    mock.post(MESSAGES_URL).mock(return_value=httpx.Response(502))

    resp = client.post("/ask", json={"question": "How was the model tested?", "thread_id": THREAD})

    data = resp.json()["data"]
    assert resp.status_code == 200
    assert data["source"] == "fallback" and data["answer"] == FALLBACK_TEXT
    assert data["thread_id"] is None


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload",
    [
        {"question": "How was the model tested?", "memory": "Auto"},  # extra=forbid
        {"question": "How was the model tested?", "assistant_id": ASSISTANT},
        {"question": "hi"},
        {"question": "x" * 301},
        {"question": "How was the model tested?", "thread_id": "not-a-uuid"},
        {},
    ],
)
def test_post_ask_rejects_bad_requests(
    ask_api: tuple[TestClient, respx.MockRouter], payload: dict[str, object]
) -> None:
    client, mock = ask_api
    messages = mock.post(MESSAGES_URL).mock(return_value=_reply())

    resp = client.post("/ask", json=payload)

    assert resp.status_code == 422
    assert resp.json()["success"] is False
    assert not messages.called


@pytest.mark.integration
@pytest.mark.parametrize(
    "over",
    [{}, {"backboard_api_key": KEY}, {"backboard_assistant_id": ASSISTANT}],
)
def test_post_ask_unavailable_without_key_or_assistant(
    bundle_dir: Path, over: dict[str, object]
) -> None:
    for client, _ in _client(bundle_dir, **over):
        resp = client.post("/ask", json={"question": "How was the model tested?"})

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "ASK_UNAVAILABLE"


@pytest.mark.unit
def test_ask_is_a_paid_route() -> None:
    assert is_paid("POST", "/ask")


@pytest.mark.unit
def test_ask_settings_defaults() -> None:
    cfg = Settings(_env_file=None)  # type: ignore[call-arg]

    assert cfg.backboard_api_key is None and cfg.backboard_assistant_id is None
    assert cfg.backboard_llm_provider == "google"
    assert cfg.backboard_model == "gemini-3.1-flash-lite"
    assert cfg.ask_daily_budget == 300


# --- check_keys ------------------------------------------------------------------------------


@pytest.mark.unit
async def test_check_backboard_missing_key() -> None:
    async with httpx.AsyncClient() as client:
        status, note = await check_backboard(client, None, None)

    assert status == MISSING and "BACKBOARD_API_KEY" in note


@pytest.mark.unit
async def test_check_backboard_reads_the_assistant() -> None:
    with respx.mock() as mock:
        route = mock.get(f"{BACKBOARD_API}/assistants/{ASSISTANT}").mock(
            return_value=httpx.Response(200, json={"assistant_id": ASSISTANT})
        )
        async with httpx.AsyncClient() as client:
            status, note = await check_backboard(client, KEY, ASSISTANT)

    assert status == OK and KEY not in note
    assert route.calls[0].request.headers["X-API-Key"] == KEY


@pytest.mark.unit
async def test_check_backboard_without_assistant_lists_assistants() -> None:
    with respx.mock() as mock:
        mock.get(f"{BACKBOARD_API}/assistants").mock(return_value=httpx.Response(200, json=[]))
        async with httpx.AsyncClient() as client:
            status, note = await check_backboard(client, KEY, None)

    assert status == OK and "BACKBOARD_ASSISTANT_ID" in note


@pytest.mark.unit
async def test_check_backboard_rejected_key() -> None:
    with respx.mock() as mock:
        mock.get(f"{BACKBOARD_API}/assistants/{ASSISTANT}").mock(return_value=httpx.Response(401))
        async with httpx.AsyncClient() as client:
            status, note = await check_backboard(client, KEY, ASSISTANT)

    assert status == FAIL and "401" in note and KEY not in note
