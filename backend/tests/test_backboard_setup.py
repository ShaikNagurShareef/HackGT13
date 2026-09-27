"""One-time Backboard setup: assistant, curated docs corpus, read-only facts. All HTTP mocked."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from app.config import Settings
from app.services.ask_corpus import CORPUS_FILES
from app.services.backboard import BACKBOARD_API, Backboard
from app.tools.setup_backboard import (
    FACT_EXTRACTION_PROMPT,
    MEMORIES,
    SYSTEM_PROMPT,
    TOK_K,
    main_async,
    run_setup,
)

KEY = "bb-setup-key-do-not-print"
ASSISTANT = "44444444-4444-4444-8444-444444444444"
BANNED_OUTSIDE_RULES = re.compile(r"\b(safest|unsafe|guaranteed)\b", re.IGNORECASE)


async def _no_sleep(_: float) -> None:
    return None


def _corpus(root: Path, names: tuple[str, ...]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {name}\nHoldout capture 74.3% vs HIN 53.8%.\n")


class FakeBackboard:
    """respx routes for the setup flow; each document is 'processing' once, then 'indexed'."""

    def __init__(self, mock: respx.MockRouter, final: str = "indexed") -> None:
        self.uploads: list[str] = []
        self.polls: dict[str, int] = {}
        self.final = final
        self.assistant = mock.post(f"{BACKBOARD_API}/assistants").mock(
            return_value=httpx.Response(200, json={"assistant_id": ASSISTANT, "name": "PathPro"})
        )
        self.upload = mock.post(f"{BACKBOARD_API}/assistants/{ASSISTANT}/documents").mock(
            side_effect=self._upload
        )
        self.status = mock.get(
            url__regex=rf"{BACKBOARD_API}/documents/(?P<doc>[\w-]+)/status"
        ).mock(side_effect=self._status)
        self.memories = mock.post(f"{BACKBOARD_API}/assistants/{ASSISTANT}/memories").mock(
            return_value=httpx.Response(201, json={"id": "m"})
        )

    def _upload(self, request: httpx.Request) -> httpx.Response:
        doc = f"doc-{len(self.uploads)}"
        match = re.search(rb'filename="([^"]+)"', request.content)
        self.uploads.append(match.group(1).decode() if match else "?")
        return httpx.Response(200, json={"document_id": doc, "status": "pending"})

    def _status(self, request: httpx.Request, doc: str) -> httpx.Response:
        self.polls[doc] = self.polls.get(doc, 0) + 1
        status = "processing" if self.polls[doc] == 1 else self.final
        return httpx.Response(200, json={"document_id": doc, "status": status})


@pytest.mark.unit
def test_system_prompt_sets_the_ground_rules() -> None:
    prompt = SYSTEM_PROMPT.lower()

    for rule in (
        "only",
        "don't know",
        "traffic risk",
        "lower-risk",
        "120 words",
        "never used for routing",
        "risk score",
        "personal",
    ):
        assert rule in prompt, rule
    assert 1 <= TOK_K <= 100


@pytest.mark.unit
def test_memories_hold_the_key_facts() -> None:
    text = " ".join(MEMORIES).lower()

    for fact in ("never", "routing", "demographic", "74.3%", "53.8%", "offline", "coding claws"):
        assert fact in text, fact
    assert "solo" in text
    assert not BANNED_OUTSIDE_RULES.search(text)


@pytest.mark.unit
def test_corpus_is_the_curated_docs() -> None:
    assert "docs/model_card.md" in CORPUS_FILES
    assert "docs/metrics.json" in CORPUS_FILES
    assert all(name.startswith("docs/") or name == "README.md" for name in CORPUS_FILES)
    assert not any(".env" in name for name in CORPUS_FILES)


@pytest.mark.unit
async def test_run_setup_creates_uploads_polls_and_remembers(tmp_path: Path) -> None:
    present = CORPUS_FILES[:3]
    _corpus(tmp_path, present)
    with respx.mock(assert_all_called=True) as mock:
        fake = FakeBackboard(mock)
        async with httpx.AsyncClient() as client:
            result = await run_setup(Backboard(client, KEY), tmp_path, sleep=_no_sleep)

    assert result.assistant_id == ASSISTANT
    created = json.loads(fake.assistant.calls[0].request.content)
    assert created["system_prompt"] == SYSTEM_PROMPT
    assert created["custom_fact_extraction_prompt"] == FACT_EXTRACTION_PROMPT
    assert created["tok_k"] == TOK_K
    assert "PathPro" in created["name"]
    assert fake.uploads == [Path(name).name for name in present]
    assert result.documents == {Path(name).name: "indexed" for name in present}
    assert result.missing == tuple(name for name in CORPUS_FILES if name not in present)
    assert fake.memories.call_count == len(MEMORIES)
    sent = [json.loads(c.request.content)["content"] for c in fake.memories.calls]
    assert sent == list(MEMORIES)
    for call in (*fake.assistant.calls, *fake.upload.calls, *fake.memories.calls):
        assert call.request.headers["X-API-Key"] == KEY


@pytest.mark.unit
async def test_run_setup_reports_documents_that_fail_to_index(tmp_path: Path) -> None:
    _corpus(tmp_path, CORPUS_FILES[:1])
    with respx.mock() as mock:
        FakeBackboard(mock, final="error")
        async with httpx.AsyncClient() as client:
            result = await run_setup(Backboard(client, KEY), tmp_path, sleep=_no_sleep)

    assert result.documents == {Path(CORPUS_FILES[0]).name: "error"}
    assert not result.all_indexed


@pytest.mark.unit
async def test_run_setup_stops_polling_after_the_limit(tmp_path: Path) -> None:
    _corpus(tmp_path, CORPUS_FILES[:1])
    with respx.mock() as mock:
        fake = FakeBackboard(mock, final="processing")
        async with httpx.AsyncClient() as client:
            result = await run_setup(Backboard(client, KEY), tmp_path, sleep=_no_sleep, max_polls=4)

    assert result.documents == {Path(CORPUS_FILES[0]).name: "processing"}
    assert fake.status.call_count == 4


@pytest.mark.unit
async def test_main_prints_only_the_assistant_id_and_statuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path, CORPUS_FILES[:2])
    cfg = Settings(backboard_api_key=KEY, _env_file=None)  # type: ignore[call-arg]
    with respx.mock() as mock:
        FakeBackboard(mock)
        code = await main_async(cfg, tmp_path, sleep=_no_sleep)

    out = capsys.readouterr().out
    assert code == 0
    assert ASSISTANT in out
    assert "BACKBOARD_ASSISTANT_ID" in out
    assert "indexed" in out
    assert KEY not in out


@pytest.mark.unit
async def test_main_without_key_makes_no_calls(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(host="app.backboard.io")
        code = await main_async(cfg, tmp_path, sleep=_no_sleep)

    assert code == 2
    assert not route.called
    assert "BACKBOARD_API_KEY" in capsys.readouterr().out


@pytest.mark.unit
async def test_main_refuses_to_duplicate_an_existing_assistant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = Settings(  # type: ignore[call-arg]
        backboard_api_key=KEY, backboard_assistant_id=ASSISTANT, _env_file=None
    )
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(host="app.backboard.io")
        code = await main_async(cfg, tmp_path, sleep=_no_sleep)

    assert code == 1
    assert not route.called
    assert "--new" in capsys.readouterr().out


@pytest.mark.unit
async def test_main_upstream_failure_prints_type_name_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path, CORPUS_FILES[:1])
    cfg = Settings(backboard_api_key=KEY, _env_file=None)  # type: ignore[call-arg]
    with respx.mock() as mock:
        mock.post(f"{BACKBOARD_API}/assistants").mock(return_value=httpx.Response(401))
        code = await main_async(cfg, tmp_path, sleep=_no_sleep)

    out = capsys.readouterr().out
    assert code == 1
    assert "HTTPStatusError" in out
    assert KEY not in out


@pytest.mark.unit
def test_system_prompt_explains_the_context_block() -> None:
    prompt = SYSTEM_PROMPT.lower()

    assert "context from pathpro's model" in prompt
    for rule in ("this street", "route", "area", "numbers", "score", "never rank"):
        assert rule in prompt, rule


@pytest.mark.unit
def test_fact_extraction_keeps_only_stated_preferences() -> None:
    prompt = FACT_EXTRACTION_PROMPT.lower()

    for kept in (
        "preferences",
        "travel time",
        "travel mode",
        "well-lit",
        "busier",
        "accessibility",
    ):
        assert kept in prompt, kept
    for never in ("places", "addresses", "street names", "routes", "coordinates"):
        assert never in prompt, never
    assert "never" in prompt and "only" in prompt
    assert "context from pathpro's model" in prompt
    assert not BANNED_OUTSIDE_RULES.search(prompt)


@pytest.mark.unit
def test_fact_prompt_uses_the_structured_json_format_with_examples() -> None:
    # Backboard ignored a prose-only prompt live (nothing was ever extracted); the
    # {"facts": [...]} format with examples was verified to keep preferences and drop addresses.
    assert '{"facts": [' in FACT_EXTRACTION_PROMPT
    assert "Input:" in FACT_EXTRACTION_PROMPT and "Output:" in FACT_EXTRACTION_PROMPT
    assert '{"facts": []}' in FACT_EXTRACTION_PROMPT  # addresses and context blocks give nothing
