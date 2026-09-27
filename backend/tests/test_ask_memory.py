"""Ask PathPro opt-in private memory: one Backboard assistant clone per browser, Forget me.

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
from app.services.ask_memory import (
    ASK_MEMORY_PER_CLIENT_DAILY,
    CLONE_PREFIX,
    AskMemory,
)
from app.services.ask_threads import MemoryTokens
from app.services.backboard import BACKBOARD_API, Backboard
from app.services.weather import FORECAST_URL
from fastapi.testclient import TestClient

from tests.test_ask import (
    ASSISTANT,
    CLIENT,
    GOOD,
    KEY,
    MESSAGES_URL,
    SECRET,
    THREAD,
    THREADS_URL,
    TOKEN_RE,
    TOKENS,
    _body,
    _reply,
    _service,
)

CLONE = "55555555-5555-4555-8555-555555555555"
MEMORY = MemoryTokens(SECRET)
CLONE_URL = f"{BACKBOARD_API}/assistants/{ASSISTANT}/clone"
CLONE_THREADS_URL = f"{BACKBOARD_API}/assistants/{CLONE}/threads"
DELETE_URL = f"{BACKBOARD_API}/assistants/{CLONE}"
CLONE_NAME_RE = re.compile(rf"^{CLONE_PREFIX}[0-9a-f]{{12}}$")


def _clone_reply(assistant_id: str = CLONE) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "assistant": {"assistant_id": assistant_id, "name": "pathpro-visitor-x"},
            "documents_cloned": 6,
            "memories_cloned": 5,
        },
    )


def _memory(client: httpx.AsyncClient, **over: int) -> AskMemory:
    kw = {"daily_budget": 100, "per_client_daily": ASK_MEMORY_PER_CLIENT_DAILY}
    kw.update(over)
    return AskMemory(Backboard(client, KEY), ASSISTANT, MEMORY, **kw)


# --- tokens ------------------------------------------------------------------------------------


@pytest.mark.unit
def test_memory_token_is_uuid_dot_signature() -> None:
    token = MEMORY.issue(CLONE)

    assert TOKEN_RE.match(token) and token.startswith(CLONE + ".")
    assert MEMORY.verify(token) == CLONE
    assert MemoryTokens(SECRET).verify(token) == CLONE  # same secret: survives a restart


@pytest.mark.unit
def test_thread_and_memory_tokens_are_not_interchangeable() -> None:
    assert MEMORY.verify(TOKENS.issue(CLONE)) is None
    assert MEMORY.verify(TOKENS.issue(CLONE, ASSISTANT)) is None
    assert TOKENS.verify(MEMORY.issue(THREAD)) is None
    assert TOKENS.verify(MEMORY.issue(THREAD), ASSISTANT) is None


@pytest.mark.unit
def test_thread_tokens_bind_the_assistant() -> None:
    token = TOKENS.issue(THREAD, ASSISTANT)

    assert TOKENS.verify(token, ASSISTANT) == THREAD
    assert TOKENS.verify(token, CLONE) is None  # a base thread cannot move to a clone
    assert TOKENS.verify(token) is None
    assert TOKENS.verify(TOKENS.issue(THREAD, CLONE), ASSISTANT) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad",
    [None, "", CLONE, CLONE + "." + "A" * 43, "not-a-token", MemoryTokens(b"z" * 32).issue(CLONE)],
)
def test_memory_token_rejects_bare_forged_or_foreign(bad: str | None) -> None:
    assert MEMORY.verify(bad) is None


# --- Backboard client --------------------------------------------------------------------------


@pytest.mark.unit
async def test_clone_assistant_copies_documents_and_memories() -> None:
    with respx.mock() as mock:
        route = mock.post(CLONE_URL).mock(return_value=_clone_reply())
        async with httpx.AsyncClient() as client:
            clone = await Backboard(client, KEY).clone_assistant(ASSISTANT, "pathpro-visitor-ab")

    assert clone == CLONE
    assert json.loads(route.calls[0].request.content) == {
        "name": "pathpro-visitor-ab",
        "copy_documents": True,
        "copy_memories": True,
    }
    assert route.calls[0].request.headers["X-API-Key"] == KEY


@pytest.mark.unit
async def test_delete_and_list_assistants() -> None:
    listing = [{"assistant_id": CLONE, "name": "pathpro-visitor-ab", "created_at": "2026-01-01"}]
    with respx.mock() as mock:
        delete = mock.delete(DELETE_URL).mock(return_value=httpx.Response(204))
        listed = mock.get(f"{BACKBOARD_API}/assistants").mock(
            return_value=httpx.Response(200, json=listing)
        )
        async with httpx.AsyncClient() as client:
            backboard = Backboard(client, KEY)
            await backboard.delete_assistant(CLONE)
            assistants = await backboard.list_assistants(skip=0, limit=100)

    assert delete.called and delete.calls[0].request.headers["X-API-Key"] == KEY
    assert assistants == listing
    assert listed.calls[0].request.url.params["limit"] == "100"


# --- enabling memory ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_enable_clones_the_base_assistant_and_signs_the_clone() -> None:
    with respx.mock() as mock:
        route = mock.post(CLONE_URL).mock(return_value=_clone_reply())
        async with httpx.AsyncClient() as client:
            token = await _memory(client).enable(CLIENT)

    assert MEMORY.verify(token) == CLONE
    body = json.loads(route.calls[0].request.content)
    assert CLONE_NAME_RE.match(body["name"])
    assert body["copy_documents"] is True and body["copy_memories"] is True


@pytest.mark.unit
async def test_enable_is_capped_per_client_before_the_global_budget() -> None:
    with respx.mock() as mock:
        route = mock.post(CLONE_URL).mock(return_value=_clone_reply())
        async with httpx.AsyncClient() as client:
            memory = _memory(client, daily_budget=4)
            for _ in range(ASK_MEMORY_PER_CLIENT_DAILY):
                await memory.enable("a")
            with pytest.raises(AppError) as err:
                await memory.enable("a")
            await memory.enable("b")  # the shared budget was not spent by the capped client

    assert ASK_MEMORY_PER_CLIENT_DAILY == 3
    assert err.value.code == "ASK_MEMORY_LIMIT" and err.value.status == 429
    assert route.call_count == 4


@pytest.mark.unit
async def test_enable_is_capped_globally() -> None:
    with respx.mock() as mock:
        route = mock.post(CLONE_URL).mock(return_value=_clone_reply())
        async with httpx.AsyncClient() as client:
            memory = _memory(client, daily_budget=1)
            await memory.enable("a")
            with pytest.raises(AppError) as err:
                await memory.enable("b")

    assert err.value.code == "ASK_MEMORY_LIMIT" and err.value.status == 429
    assert route.call_count == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, json={"assistant": {}}),
        httpx.Response(200, json={"assistant": {"assistant_id": "not-a-uuid"}}),
        httpx.Response(200, json={"assistant": {"assistant_id": ASSISTANT}}),  # never the base
    ],
)
async def test_enable_upstream_failure_is_a_502(
    response: httpx.Response, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with respx.mock() as mock:
        mock.post(CLONE_URL).mock(return_value=response)
        async with httpx.AsyncClient() as client:
            with pytest.raises(AppError) as err:
                await _memory(client).enable(CLIENT)

    assert err.value.code == "ASK_MEMORY_FAILED" and err.value.status == 502
    assert KEY not in caplog.text


@pytest.mark.unit
async def test_enable_without_backboard_is_unavailable() -> None:
    memory = AskMemory(None, ASSISTANT, MEMORY)
    with pytest.raises(AppError) as err:
        await memory.enable(CLIENT)

    assert err.value.code == "ASK_UNAVAILABLE" and err.value.status == 503


# --- forgetting --------------------------------------------------------------------------------


@pytest.mark.unit
async def test_forget_deletes_the_clone() -> None:
    with respx.mock() as mock:
        delete = mock.delete(DELETE_URL).mock(return_value=httpx.Response(200, json={}))
        async with httpx.AsyncClient() as client:
            await _memory(client).forget(MEMORY.issue(CLONE))

    assert delete.call_count == 1


@pytest.mark.unit
async def test_forget_an_already_deleted_clone_is_fine() -> None:
    with respx.mock() as mock:
        mock.delete(DELETE_URL).mock(return_value=httpx.Response(404))
        async with httpx.AsyncClient() as client:
            await _memory(client).forget(MEMORY.issue(CLONE))


@pytest.mark.unit
@pytest.mark.parametrize(
    "token",
    [
        CLONE,
        CLONE + "." + "A" * 43,
        TOKENS.issue(CLONE, ASSISTANT),  # a thread token is not a memory token
        MemoryTokens(b"z" * 32).issue(CLONE),
        MEMORY.issue(ASSISTANT),  # the shared base assistant is never deleted
        "",
    ],
)
async def test_forget_with_an_invalid_token_never_calls_upstream(token: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(host="app.backboard.io")
        async with httpx.AsyncClient() as client:
            await _memory(client).forget(token)

    assert not route.called


@pytest.mark.unit
@pytest.mark.parametrize("response", [httpx.Response(500), httpx.Response(401)])
async def test_forget_upstream_failure_is_a_502(response: httpx.Response) -> None:
    with respx.mock() as mock:
        mock.delete(DELETE_URL).mock(return_value=response)
        async with httpx.AsyncClient() as client:
            with pytest.raises(AppError) as err:
                await _memory(client).forget(MEMORY.issue(CLONE))

    assert err.value.code == "ASK_MEMORY_FORGET_FAILED" and err.value.status == 502


# --- asking with memory ------------------------------------------------------------------------


@pytest.mark.unit
async def test_valid_memory_token_uses_the_clone_with_auto_memory() -> None:
    with respx.mock(assert_all_called=True) as mock:
        threads = mock.post(CLONE_THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            answer = await _service(client, memory_tokens=MEMORY).ask(
                "How was the model tested?", None, client=CLIENT, memory_token=MEMORY.issue(CLONE)
            )

    assert threads.call_count == 1
    body = _body(messages)
    assert body["assistant_id"] == CLONE and body["memory"] == "Auto"
    assert answer.memory == "on" and answer.source == "backboard"
    assert answer.thread_id == TOKENS.issue(THREAD, CLONE)


@pytest.mark.unit
@pytest.mark.parametrize(
    "token",
    [None, CLONE, CLONE + "." + "A" * 43, TOKENS.issue(CLONE, ASSISTANT), "junk"],
)
async def test_missing_or_invalid_memory_token_uses_the_base_read_only(token: str | None) -> None:
    with respx.mock() as mock:
        mock.post(THREADS_URL).mock(return_value=httpx.Response(200, json={"thread_id": THREAD}))
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            answer = await _service(client, memory_tokens=MEMORY).ask(
                "How was the model tested?", None, client=CLIENT, memory_token=token
            )

    body = _body(messages)
    assert body["assistant_id"] == ASSISTANT and body["memory"] == "Readonly"
    assert answer.memory == "off"
    assert answer.thread_id == TOKENS.issue(THREAD, ASSISTANT)


@pytest.mark.unit
async def test_a_base_thread_is_not_continued_on_the_clone() -> None:
    with respx.mock(assert_all_called=True) as mock:
        threads = mock.post(CLONE_THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            await _service(client, memory_tokens=MEMORY).ask(
                "Tell me more",
                TOKENS.issue(THREAD, ASSISTANT),
                client=CLIENT,
                memory_token=MEMORY.issue(CLONE),
            )

    assert threads.call_count == 1  # a new thread on the clone
    assert _body(messages)["assistant_id"] == CLONE


@pytest.mark.unit
async def test_a_clone_thread_is_not_continued_on_the_base() -> None:
    with respx.mock(assert_all_called=True) as mock:
        threads = mock.post(THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            await _service(client, memory_tokens=MEMORY).ask(
                "Tell me more", TOKENS.issue(THREAD, CLONE), client=CLIENT
            )

    assert threads.call_count == 1
    assert _body(messages)["assistant_id"] == ASSISTANT


@pytest.mark.unit
async def test_a_clone_thread_continues_with_memory_on() -> None:
    with respx.mock() as mock:
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            answer = await _service(client, memory_tokens=MEMORY).ask(
                "Tell me more",
                TOKENS.issue(THREAD, CLONE),
                client=CLIENT,
                memory_token=MEMORY.issue(CLONE),
            )

    body = _body(messages)
    assert body["thread_id"] == THREAD and body["assistant_id"] == CLONE
    assert answer.thread_id == TOKENS.issue(THREAD, CLONE)


@pytest.mark.unit
async def test_memory_tokens_and_clone_ids_are_never_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    token = MEMORY.issue(CLONE)
    with respx.mock() as mock:
        mock.post(CLONE_THREADS_URL).mock(side_effect=httpx.ConnectError("boom"))
        mock.delete(DELETE_URL).mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            await _service(client, memory_tokens=MEMORY).ask(
                "How was the model tested?", None, client=CLIENT, memory_token=token
            )
            with pytest.raises(AppError):
                await _memory(client).forget(token)

    assert token not in caplog.text and CLONE not in caplog.text


# --- API ---------------------------------------------------------------------------------------


def _app(bundle_dir: Path, **over: object) -> Iterator[tuple[TestClient, respx.MockRouter]]:
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


CONFIGURED = {
    "backboard_api_key": KEY,
    "backboard_assistant_id": ASSISTANT,
    "ask_thread_secret": SECRET.decode(),
}


@pytest.fixture
def api(bundle_dir: Path) -> Iterator[tuple[TestClient, respx.MockRouter]]:
    yield from _app(bundle_dir, **CONFIGURED)


@pytest.mark.integration
def test_post_ask_memory_returns_a_signed_memory_token(
    api: tuple[TestClient, respx.MockRouter],
) -> None:
    client, mock = api
    clone = mock.post(CLONE_URL).mock(return_value=_clone_reply())

    resp = client.post("/ask/memory", json={})

    assert resp.status_code == 200
    token = resp.json()["data"]["memory_token"]
    assert TOKEN_RE.match(token) and MEMORY.verify(token) == CLONE
    assert clone.call_count == 1


@pytest.mark.integration
def test_post_ask_memory_per_client_cap_is_a_429(
    api: tuple[TestClient, respx.MockRouter],
) -> None:
    client, mock = api
    clone = mock.post(CLONE_URL).mock(return_value=_clone_reply())

    codes = [client.post("/ask/memory", json={}).status_code for _ in range(4)]
    last = client.post("/ask/memory", json={}).json()

    assert codes == [200, 200, 200, 429]
    assert last["error"]["code"] == "ASK_MEMORY_LIMIT"
    assert clone.call_count == 3


@pytest.mark.integration
def test_post_ask_memory_global_cap(bundle_dir: Path) -> None:
    for client, mock in _app(bundle_dir, ask_memory_daily=1, **CONFIGURED):
        mock.post(CLONE_URL).mock(return_value=_clone_reply())

        first = client.post("/ask/memory", json={})
        second = client.post("/ask/memory", json={})

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "ASK_MEMORY_LIMIT"


@pytest.mark.integration
def test_post_ask_memory_unavailable_without_backboard(bundle_dir: Path) -> None:
    for client, _ in _app(bundle_dir):
        resp = client.post("/ask/memory", json={})

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "ASK_UNAVAILABLE"


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload", [{"name": "mine"}, {"copy_memories": False}, {"assistant_id": ASSISTANT}]
)
def test_post_ask_memory_takes_no_options(
    api: tuple[TestClient, respx.MockRouter], payload: dict[str, object]
) -> None:
    client, mock = api
    clone = mock.post(CLONE_URL).mock(return_value=_clone_reply())

    assert client.post("/ask/memory", json=payload).status_code == 422
    assert not clone.called


@pytest.mark.integration
def test_post_ask_with_memory_token_uses_the_clone(
    api: tuple[TestClient, respx.MockRouter],
) -> None:
    client, mock = api
    mock.post(CLONE_URL).mock(return_value=_clone_reply())
    mock.post(CLONE_THREADS_URL).mock(return_value=httpx.Response(200, json={"thread_id": THREAD}))
    messages = mock.post(MESSAGES_URL).mock(return_value=_reply(GOOD))
    token = client.post("/ask/memory", json={}).json()["data"]["memory_token"]

    data = client.post(
        "/ask", json={"question": "How was the model tested?", "memory_token": token}
    ).json()["data"]

    assert data["memory"] == "on"
    assert _body(messages)["assistant_id"] == CLONE and _body(messages)["memory"] == "Auto"
    assert TOKENS.verify(data["thread_id"], CLONE) == THREAD


@pytest.mark.integration
def test_post_ask_with_forged_memory_token_is_memory_off(
    api: tuple[TestClient, respx.MockRouter],
) -> None:
    client, mock = api
    mock.post(THREADS_URL).mock(return_value=httpx.Response(200, json={"thread_id": THREAD}))
    messages = mock.post(MESSAGES_URL).mock(return_value=_reply(GOOD))

    resp = client.post(
        "/ask",
        json={"question": "How was the model tested?", "memory_token": CLONE + "." + "A" * 43},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["memory"] == "off"
    assert _body(messages)["assistant_id"] == ASSISTANT
    assert _body(messages)["memory"] == "Readonly"


@pytest.mark.integration
def test_post_ask_rejects_an_oversized_memory_token(
    api: tuple[TestClient, respx.MockRouter],
) -> None:
    client, _ = api

    resp = client.post(
        "/ask", json={"question": "How was the model tested?", "memory_token": "x" * 129}
    )

    assert resp.status_code == 422


@pytest.mark.integration
def test_post_forget_deletes_the_clone(api: tuple[TestClient, respx.MockRouter]) -> None:
    client, mock = api
    delete = mock.delete(DELETE_URL).mock(return_value=httpx.Response(200, json={}))

    resp = client.post("/ask/memory/forget", json={"memory_token": MEMORY.issue(CLONE)})

    assert resp.status_code == 200
    assert resp.json()["data"] == {"forgotten": True}
    assert delete.call_count == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    "token", [CLONE, CLONE + "." + "A" * 43, TOKENS.issue(CLONE, ASSISTANT), "junk"]
)
def test_post_forget_with_invalid_token_is_idempotent_and_silent(
    api: tuple[TestClient, respx.MockRouter], token: str
) -> None:
    client, mock = api
    delete = mock.delete(url__regex=rf"{BACKBOARD_API}/assistants/.*").mock(
        return_value=httpx.Response(200, json={})
    )

    resp = client.post("/ask/memory/forget", json={"memory_token": token})

    assert resp.status_code == 200 and resp.json()["data"] == {"forgotten": True}
    assert not delete.called


@pytest.mark.integration
def test_post_forget_upstream_failure_is_a_502(api: tuple[TestClient, respx.MockRouter]) -> None:
    client, mock = api
    mock.delete(DELETE_URL).mock(return_value=httpx.Response(503))

    resp = client.post("/ask/memory/forget", json={"memory_token": MEMORY.issue(CLONE)})

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "ASK_MEMORY_FORGET_FAILED"


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload",
    [{}, {"memory_token": 7}, {"memory_token": "x" * 129}, {"memory_token": "a", "all": True}],
)
def test_post_forget_rejects_bad_bodies(
    api: tuple[TestClient, respx.MockRouter], payload: dict[str, object]
) -> None:
    client, _ = api

    assert client.post("/ask/memory/forget", json=payload).status_code == 422


@pytest.mark.unit
def test_memory_routes_are_paid() -> None:
    assert is_paid("POST", "/ask/memory")
    assert is_paid("POST", "/ask/memory/forget")


@pytest.mark.unit
def test_memory_settings_defaults_and_env_example() -> None:
    cfg = Settings(_env_file=None)  # type: ignore[call-arg]
    example = (BACKEND_DIR.parent / ".env.example").read_text(encoding="utf-8")

    assert cfg.ask_memory_daily == 100
    assert "ASK_MEMORY_DAILY=100" in example


@pytest.mark.integration
def test_memory_tokens_work_with_the_per_process_secret(bundle_dir: Path) -> None:
    over = {"backboard_api_key": KEY, "backboard_assistant_id": ASSISTANT}
    for client, mock in _app(bundle_dir, **over):
        mock.post(CLONE_URL).mock(return_value=_clone_reply())
        mock.post(CLONE_THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply(GOOD))
        token = client.post("/ask/memory", json={}).json()["data"]["memory_token"]

        data = client.post(
            "/ask", json={"question": "How was the model tested?", "memory_token": token}
        ).json()["data"]

        assert data["memory"] == "on"
        assert _body(messages)["assistant_id"] == CLONE


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kind", "expected"),
    [("segment", "Readonly"), ("route", "Readonly"), ("area", "Readonly"), ("conditions", "Auto")],
)
async def test_context_questions_never_write_memory_even_on_a_clone(
    kind: str, expected: str
) -> None:
    from app.services.explain.evidence import _with_numbers

    evidence = _with_numbers(kind, {"time": "9 PM", "conditions": "dry"})
    with respx.mock(assert_all_called=True) as mock:
        mock.post(CLONE_THREADS_URL).mock(
            return_value=httpx.Response(200, json={"thread_id": THREAD})
        )
        messages = mock.post(MESSAGES_URL).mock(return_value=_reply())
        async with httpx.AsyncClient() as client:
            answer = await _service(client, memory_tokens=MEMORY).ask(
                "How was the model tested?",
                None,
                client=CLIENT,
                evidence=evidence,
                memory_token=MEMORY.issue(CLONE),
            )

    body = _body(messages)
    assert body["assistant_id"] == CLONE and body["memory"] == expected
    assert answer.memory == "on"


@pytest.mark.unit
def test_memory_per_client_cap_is_configurable(bundle_dir: Path) -> None:
    # The expo venue shares one address, so the per-address cap must be tunable in production.
    settings = Settings(artifacts_dir=bundle_dir, ask_memory_per_client_daily=7, _env_file=None)

    assert settings.ask_memory_per_client_daily == 7
    assert Settings(artifacts_dir=bundle_dir, _env_file=None).ask_memory_per_client_daily == 3
