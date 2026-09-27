"""Ask PathPro: Backboard-backed Q&A about PathPro's own docs, validated before it is shown.

Every Backboard call is mocked with respx; the real API is never contacted.
"""

from __future__ import annotations

import json
import logging
import re
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
    CLIENT_LIMIT_MESSAGE,
    FALLBACK_TEXT,
    AskService,
    clean_question,
)
from app.services.ask_corpus import allowed_numbers, load_allowed_numbers
from app.services.ask_threads import ThreadTokens
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
SECRET = b"k" * 32
TOKENS = ThreadTokens(SECRET)
TOKEN_RE = re.compile(r"^[0-9a-f-]{36}\.[A-Za-z0-9_-]{22,}$")
CLIENT = "203.0.113.7"
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
        "per_client_daily": 20,
        "thread_tokens": TOKENS,
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


# --- signed thread tokens --------------------------------------------------------------------


@pytest.mark.unit
def test_thread_token_is_uuid_dot_signature() -> None:
    token = TOKENS.issue(THREAD)

    assert TOKEN_RE.match(token), token
    assert token.startswith(THREAD + ".")
    assert TOKENS.verify(token) == THREAD
    assert ThreadTokens(SECRET).verify(token) == THREAD  # same secret: survives a restart


@pytest.mark.unit
def test_thread_token_signature_is_long_enough() -> None:
    sig = TOKENS.issue(THREAD).split(".", 1)[1]

    assert len(sig) >= 22


@pytest.mark.unit
def test_thread_token_is_canonicalized_before_signing() -> None:
    assert TOKENS.issue(THREAD.upper()) == TOKENS.issue(THREAD)


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        THREAD,  # a bare Backboard thread id is never accepted
        THREAD.upper(),
        "not-a-uuid",
        "../../assistants",
        THREAD + ".",
        THREAD + ".short",
        THREAD + "." + "A" * 43,  # forged signature
        OTHER_THREAD + "." + "x",
    ],
)
def test_thread_token_rejects_bare_forged_or_malformed(bad: str | None) -> None:
    assert TOKENS.verify(bad) is None


@pytest.mark.unit
def test_thread_token_signature_is_bound_to_the_uuid_and_secret() -> None:
    sig = TOKENS.issue(THREAD).split(".", 1)[1]

    assert TOKENS.verify(f"{OTHER_THREAD}.{sig}") is None  # signature moved to another thread
    assert ThreadTokens(b"z" * 32).verify(TOKENS.issue(THREAD)) is None  # another secret
    tampered = TOKENS.issue(THREAD)[:-1] + ("A" if TOKENS.issue(THREAD)[-1] != "A" else "B")
    assert TOKENS.verify(tampered) is None
    upper = TOKENS.issue(THREAD).replace(THREAD, THREAD.upper())
    assert TOKENS.verify(upper) is None  # only the canonical form the server issued


@pytest.mark.unit
def test_random_thread_tokens_differ_per_instance() -> None:
    first, second = ThreadTokens.random(), ThreadTokens.random()

    assert first.verify(first.issue(THREAD)) == THREAD
    assert second.verify(first.issue(THREAD)) is None


@pytest.mark.unit
def test_thread_tokens_need_a_real_secret() -> None:
    with pytest.raises(ValueError):
        ThreadTokens(b"")


# --- answer validation -----------------------------------------------------------------------


@pytest.mark.unit
def test_allowed_numbers_tolerate_formatting() -> None:
    for value in (74.3, 53.8, 2024.0, 10.0, 1250.0, 41.2, 54.0):
        assert value in ALLOWED, value
    assert ask_validation_errors(GOOD, ALLOWED) == []
    text = "The model held 74.3 percent; routes had about 54% less exposure."
    assert ask_validation_errors(text, ALLOWED) == []
    assert ask_validation_errors("The data covers 1,250 street segments.", ALLOWED) == []


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
@pytest.mark.parametrize(
    "text",
    [
        "PathPro's model card is at https://example.com/model.",
        "See http://pathpro.example for the route details.",
        "Read about the traffic risk model at www.example.org.",
        "The PathPro model card lives on example.com.",
        "PathPro route docs: docs.pathpro-help.io/guide",
        "Email the PathPro team at help@example.com about the model.",
        "Message @pathpro about the model.",
        "The PathPro model is on pathpro.tech.evil.com too.",
        "The PathPro model is on notpathpro.tech too.",
        "The PathPro model is on evil-pathpro.tech too.",
        "The PathPro model is on pathpro.tech/x.evil.com too.",
        "The PathPro route model is described at HTTPS://EXAMPLE.COM.",
    ],
)
def test_validator_rejects_links_domains_and_emails(text: str) -> None:
    assert "link" in ask_validation_errors(text, ALLOWED)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "The PathPro model card is at pathpro.tech.",
        "The model card is on https://pathpro.tech under About PathPro.",
        "Open www.pathpro.tech and tap About PathPro to read how the model was tested.",
        "The route is scored per street, e.g. by speed and lanes.",
    ],
)
def test_validator_allows_the_pathpro_domain_and_ordinary_abbreviations(text: str) -> None:
    assert ask_validation_errors(text, ALLOWED) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "The weather in Paris is lovely in spring.",
        "Here is a poem about the sea and the moon.",
        "Bananas are rich in potassium.",
        "Visit pathpro.tech for more.",  # the allowed domain alone does not make it on-topic
        "Stockholm has a lovely old town.",  # contains no PathPro term, only lookalike letters
        "They provide overrides for it.",  # 'ride' inside another word does not count
    ],
)
def test_validator_rejects_off_topic_answers(text: str) -> None:
    assert "off_topic" in ask_validation_errors(text, ALLOWED)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "PathPro explains itself.",
        "Traffic risk is estimated per hour.",
        "Traffic-risk scores are estimated per hour.",
        "Routes are compared side by side.",
        "Crashes from recent years are used.",
        "The model was tested on held-out data.",
        "Every street gets its own estimate.",
        "Walking directions come first.",
        "Rides use a separate estimate.",
        "MARTA stations are shown on the map.",
        "The high injury network is the city's own list.",
        "Each score has a confidence label.",
        "Lighting only matters after dark.",
        "Help points are shown on the map.",
        "risk tides show the day's rhythm.",
        "city pulse groups the map into cells.",
        "Share my walk sends a live link.",
    ],
)
def test_validator_accepts_each_pathpro_topic_term(text: str) -> None:
    assert "off_topic" not in ask_validation_errors(text, ALLOWED)


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
            answer = await _service(client).ask("How was the model tested?", None, client=CLIENT)

    assert answer.source == "backboard"
    assert answer.text == GOOD
    assert answer.thread_id == TOKENS.issue(THREAD)  # signed token, never the bare Backboard id
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
            answer = await _service(client).ask(
                "Tell me more", TOKENS.issue(OTHER_THREAD), client=CLIENT
            )

    assert not threads.called
    assert _body(messages)["thread_id"] == OTHER_THREAD
    assert _body(messages)["memory"] == "Readonly"
    assert answer.thread_id == TOKENS.issue(OTHER_THREAD)


@pytest.mark.unit
async def test_empty_model_uses_backboard_default() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            await _service(client, model_name="").ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

    body = _body(messages)
    assert "model_name" not in body and "llm_provider" not in body


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "PathPro is 97.5% accurate.",  # invented number
        "The lower-risk route is the safest way home.",  # banned word
        "PathPro avoids high-crime neighborhoods.",  # crime framing
        "PathPro's model card moved to https://example.com/card.",  # link
        "Email help@example.com to ask about the PathPro model.",  # email
        "The weather in Paris is lovely in spring.",  # off topic
    ],
)
async def test_rejected_answers_become_the_fallback(content: str) -> None:
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=_reply(content))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

    assert answer.source == "fallback"
    assert answer.text == FALLBACK_TEXT
    assert content not in answer.text
    # The thread still works; only this answer was withheld.
    assert answer.thread_id == TOKENS.issue(THREAD)


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
            answer = await _service(client).ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

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
            answer = await _service(client).ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

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
            await _service(client).ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

    assert "97.5% guaranteed" not in caplog.text


@pytest.mark.unit
async def test_daily_budget_caps_backboard_calls() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            service = _service(client, daily_budget=1)
            first = await service.ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )
            second = await service.ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

    assert first.source == "backboard"
    assert second.source == "fallback"
    assert messages.call_count == 1


@pytest.mark.unit
async def test_budget_fallback_keeps_the_verified_thread_token() -> None:
    with respx.mock():
        async with httpx.AsyncClient() as client:
            service = _service(client, daily_budget=0)
            answer = await service.ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )
            forged = await service.ask("How was the model tested?", THREAD, client=CLIENT)

    assert answer.source == "fallback" and answer.thread_id == TOKENS.issue(THREAD)
    assert forged.source == "fallback" and forged.thread_id is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "token",
    [
        OTHER_THREAD,  # bare Backboard id
        OTHER_THREAD + "." + "A" * 43,  # forged signature
        ThreadTokens(b"z" * 32).issue(OTHER_THREAD),  # issued before a restart / by another secret
        "not-a-token",
    ],
)
async def test_unverified_thread_is_never_forwarded_upstream(
    token: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with respx.mock(assert_all_called=True) as mock:
        threads = mock.post(THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask("Tell me more", token, client=CLIENT)

    assert threads.call_count == 1  # a fresh conversation, not an error
    assert _body(messages)["thread_id"] == THREAD
    assert OTHER_THREAD not in messages.calls[0].request.content.decode()
    assert answer.source == "backboard"
    assert answer.thread_id == TOKENS.issue(THREAD)
    assert token not in caplog.text and OTHER_THREAD not in caplog.text


@pytest.mark.unit
async def test_thread_tokens_are_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    token = TOKENS.issue(THREAD)
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=_reply("It is 97.5% guaranteed."))
        async with httpx.AsyncClient() as client:
            await _service(client).ask("How was the model tested?", token, client=CLIENT)
            await _service(client, daily_budget=0).ask(
                "How was the model tested?", token, client=CLIENT
            )

    assert token not in caplog.text
    assert THREAD not in caplog.text


@pytest.mark.unit
async def test_per_client_daily_cap_returns_ask_client_limit() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            service = _service(client, per_client_daily=1)
            first = await service.ask("How was the model tested?", TOKENS.issue(THREAD), client="a")
            with pytest.raises(AppError) as err:
                await service.ask("How was the model tested?", TOKENS.issue(THREAD), client="a")
            other = await service.ask("How was the model tested?", TOKENS.issue(THREAD), client="b")

    assert first.source == "backboard" and other.source == "backboard"
    assert err.value.code == "ASK_CLIENT_LIMIT" and err.value.status == 429
    assert err.value.message == CLIENT_LIMIT_MESSAGE
    assert messages.call_count == 2


@pytest.mark.unit
async def test_per_client_cap_is_checked_before_the_global_budget() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            service = _service(client, per_client_daily=1, daily_budget=2)
            await service.ask("How was the model tested?", TOKENS.issue(THREAD), client="a")
            for _ in range(3):  # over the per-client cap: must not spend the shared budget
                with pytest.raises(AppError):
                    await service.ask("How was the model tested?", TOKENS.issue(THREAD), client="a")
            other = await service.ask("How was the model tested?", TOKENS.issue(THREAD), client="b")

    assert other.source == "backboard"
    assert messages.call_count == 2


@pytest.mark.unit
def test_client_limit_message_is_friendly() -> None:
    assert "today" in CLIENT_LIMIT_MESSAGE.lower()
    assert "About PathPro" in CLIENT_LIMIT_MESSAGE


@pytest.mark.unit
async def test_citation_markers_are_stripped() -> None:
    with respx.mock() as mock:
        mock.post(MESSAGES_URL).mock(return_value=_reply(f"{GOOD}【4:0†model_card.md】 [2]"))
        async with httpx.AsyncClient() as client:
            answer = await _service(client).ask(
                "How was the model tested?", TOKENS.issue(THREAD), client=CLIENT
            )

    assert answer.source == "backboard"
    assert answer.text == GOOD


@pytest.mark.unit
async def test_service_without_key_is_disabled() -> None:
    service = AskService(None, ASSISTANT, ALLOWED, daily_budget=10)
    assert not service.enabled
    with pytest.raises(AppError) as err:
        await service.ask("How was the model tested?", None, client=CLIENT)
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
    token = body["data"].pop("thread_id")
    assert body["data"] == {
        "answer": GOOD,
        "source": "backboard",
        "note": "Answered from PathPro's model card and docs · powered by Backboard",
    }
    assert TOKEN_RE.match(token) and token.startswith(THREAD + ".")
    assert _body(messages)["memory"] == "Readonly"


@pytest.mark.integration
def test_post_ask_continues_only_a_signed_thread(
    ask_api: tuple[TestClient, respx.MockRouter],
) -> None:
    client, mock = ask_api
    threads = mock.post(THREADS_URL).mock(
        return_value=httpx.Response(200, json={"thread_id": THREAD})
    )
    messages = mock.post(MESSAGES_URL).mock(return_value=_reply())

    token = client.post("/ask", json={"question": "How was the model tested?"}).json()["data"][
        "thread_id"
    ]
    resp = client.post("/ask", json={"question": "Tell me more", "thread_id": token})

    assert resp.json()["data"]["thread_id"] == token
    assert threads.call_count == 1
    assert _body(messages)["thread_id"] == THREAD


@pytest.mark.integration
@pytest.mark.parametrize(
    "thread_id",
    [OTHER_THREAD, OTHER_THREAD + "." + "A" * 43, "not-a-uuid", "../../assistants"],
)
def test_post_ask_bare_or_forged_thread_starts_fresh(
    ask_api: tuple[TestClient, respx.MockRouter], thread_id: str
) -> None:
    client, mock = ask_api
    threads = mock.post(THREADS_URL).mock(
        return_value=httpx.Response(200, json={"thread_id": THREAD})
    )
    messages = mock.post(MESSAGES_URL).mock(return_value=_reply())

    resp = client.post("/ask", json={"question": "Tell me more", "thread_id": thread_id})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert threads.call_count == 1
    assert _body(messages)["thread_id"] == THREAD
    assert data["thread_id"] != thread_id and TOKEN_RE.match(data["thread_id"])


@pytest.mark.integration
def test_post_ask_tokens_survive_a_restart_only_with_a_configured_secret(bundle_dir: Path) -> None:
    configured = {
        "backboard_api_key": KEY,
        "backboard_assistant_id": ASSISTANT,
        "ask_thread_secret": "a-configured-secret-for-tests-0123456789",
    }
    tokens: list[str] = []
    for _ in range(2):  # two app instances: a restart
        for client, mock in _client(bundle_dir, **configured):
            mock.post(THREADS_URL).mock(
                return_value=httpx.Response(200, json={"thread_id": THREAD})
            )
            mock.post(MESSAGES_URL).mock(return_value=_reply())
            tokens.append(
                client.post("/ask", json={"question": "How was the model tested?"}).json()["data"][
                    "thread_id"
                ]
            )
    assert tokens[0] == tokens[1]
    assert tokens[0] == ThreadTokens(b"a-configured-secret-for-tests-0123456789").issue(THREAD)

    random_tokens: list[str] = []
    for _ in range(2):
        for client, mock in _client(
            bundle_dir, backboard_api_key=KEY, backboard_assistant_id=ASSISTANT
        ):
            mock.post(THREADS_URL).mock(
                return_value=httpx.Response(200, json={"thread_id": THREAD})
            )
            mock.post(MESSAGES_URL).mock(return_value=_reply())
            random_tokens.append(
                client.post("/ask", json={"question": "How was the model tested?"}).json()["data"][
                    "thread_id"
                ]
            )
    assert random_tokens[0] != random_tokens[1]  # a per-process secret when none is configured


@pytest.mark.integration
def test_post_ask_per_client_limit_is_a_429_envelope(bundle_dir: Path) -> None:
    for client, mock in _client(
        bundle_dir, backboard_api_key=KEY, backboard_assistant_id=ASSISTANT, ask_per_client_daily=1
    ):
        mock.post(THREADS_URL).mock(return_value=httpx.Response(200, json={"thread_id": THREAD}))
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())

        first = client.post("/ask", json={"question": "How was the model tested?"})
        second = client.post("/ask", json={"question": "How was the model tested?"})

        assert first.status_code == 200
        assert second.status_code == 429
        body = second.json()
        assert body["success"] is False and body["data"] is None
        assert body["error"]["code"] == "ASK_CLIENT_LIMIT"
        assert body["error"]["message"] == CLIENT_LIMIT_MESSAGE
        assert messages.call_count == 1


@pytest.mark.integration
def test_post_ask_fallback_is_still_success(ask_api: tuple[TestClient, respx.MockRouter]) -> None:
    client, mock = ask_api
    mock.post(MESSAGES_URL).mock(return_value=httpx.Response(502))

    resp = client.post(
        "/ask",
        json={"question": "How was the model tested?", "thread_id": TOKENS.issue(THREAD)},
    )

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
        {"question": "How was the model tested?", "thread_id": "x" * 129},  # transport cap
        {"question": "How was the model tested?", "thread_id": 7},
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
    assert cfg.ask_per_client_daily == 20
    assert cfg.ask_thread_secret is None


@pytest.mark.unit
def test_env_example_documents_the_ask_settings() -> None:
    example = (BACKEND_DIR.parent / ".env.example").read_text(encoding="utf-8")

    assert "ASK_PER_CLIENT_DAILY=20" in example
    assert "ASK_THREAD_SECRET=" in example


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
