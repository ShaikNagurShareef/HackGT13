"""Ask PathPro: questions about PathPro itself, answered by a Backboard assistant from its docs.

Privacy and trust rules:
- Public users can never write the shared assistant's memory: without a valid memory token
  every message goes to the shared assistant with memory="Readonly". A visitor who turned on
  private memory (see ask_memory) talks to their own clone with memory="Auto" instead.
- The browser holds only server-signed tokens (see ask_threads). A thread token is bound to its
  assistant; a bare, forged, or mismatched one is never forwarded upstream, it starts a new
  thread. An invalid memory token simply means memory is off.
- The question may carry server-built context (a street, route, area, or live conditions);
  it never includes coordinates, and it is validated against as evidence.
- Each client address gets a small daily cap, checked before the shared daily budget is spent.
- Code identifiers in an answer (lit_and_busy) become the app's labels before validation.
- The answer is shown only if it passes the explanation validator's Ask rules (on topic, no links,
  banned words, crime framing, every number found in the docs corpus). A withheld answer gets ONE
  rewrite request in the same thread (memory "Readonly", no extra budget, inside the same
  timeout); if the rewrite also fails, and on any upstream error, timeout, or spent daily budget,
  a fixed fallback points to the model card. The raw LLM text is never shown or logged. Logs
  carry exception type names and validator error categories only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Literal

import httpx

from app.api.envelope import AppError
from app.services.ask_corpus import CorpusSource, corpus_sources
from app.services.ask_memory import verified_clone
from app.services.ask_rewrite import error_kinds, humanize_identifiers, repair_request
from app.services.ask_threads import MemoryTokens, ThreadTokens
from app.services.backboard import Backboard, BackboardError, MemoryMode
from app.services.explain.evidence import Evidence
from app.services.explain.service import DailyBudget
from app.services.explain.validator import ask_validation_errors
from app.services.limits import ClientDailyLimit

log = logging.getLogger(__name__)

TIMEOUT_S = 12.0
# A rewrite is requested only if at least this much of the ask's timeout is left.
MIN_REPAIR_S = 1.0
MIN_QUESTION_CHARS = 3
MAX_QUESTION_CHARS = 300
COMPLETED = "COMPLETED"
ASK_NOTE = "Answered from PathPro's model card and docs · powered by Backboard"
FALLBACK_NOTE = "From PathPro's model card"
FALLBACK_TEXT = (
    "I can't answer that one right now. The model card under About PathPro explains how "
    "traffic risk is scored, how the model was tested, and which data it uses."
)
UNAVAILABLE_MESSAGE = "Ask PathPro is unavailable right now. About PathPro has the model card."
CLIENT_LIMIT_MESSAGE = (
    "You've asked a lot of questions today. Please try again tomorrow; "
    "About PathPro has the model card in the meantime."
)
DEFAULT_PER_CLIENT_DAILY = 20
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# Retrieval citation markers such as 【4:0†model_card.md】 or [2] are not part of the answer.
_CITATION_RE = re.compile(r"【[^】]*】|\[\d{1,3}\]")
_BOLD_RE = re.compile(r"\*\*|__")
ASK_ERRORS = (httpx.HTTPError, BackboardError, TimeoutError)
Source = Literal["backboard", "fallback"]
MemoryState = Literal["on", "off"]
# Server-built evidence rides above the question; the assistant is told to use it only for
# this question, and the memory prompt forbids keeping anything inside this block.
CONTEXT_HEADER = "Context from PathPro's model (for this question only):"
# Sent only to a visitor's private clone: the assistant may keep stated travel preferences.
MEMORY_NOTE = (
    "Memory is on for this person (they opted in). Remember only travel preferences they state "
    "(usual times, travel mode, well-lit or busier streets, accessibility needs), never places. "
    "When they share one, confirm briefly that you'll remember it until they tap Forget me. "
    "Never say you don't store or remember their preferences."
)


@dataclass(frozen=True)
class AskAnswer:
    text: str
    thread_id: str | None  # a signed thread token, never a bare Backboard thread id
    source: Source
    sources_note: str
    sources: tuple[CorpusSource, ...] = ()  # allow-listed docs the answer cited
    memory: MemoryState = "off"


def clean_question(raw: str) -> str:
    """Trimmed question text; 3-300 characters with no control characters."""
    question = raw.strip()
    if _CONTROL_RE.search(question):
        raise AppError("BAD_QUESTION", "Please ask on a single line of plain text.", 422)
    if not MIN_QUESTION_CHARS <= len(question) <= MAX_QUESTION_CHARS:
        raise AppError("BAD_QUESTION", "Questions need 3 to 300 characters.", 422)
    return question


def compose_content(question: str, evidence: Evidence | None, *, memory_on: bool = False) -> str:
    """The message sent upstream: memory note, context block (compact JSON), then the question."""
    parts = [MEMORY_NOTE] if memory_on else []
    if evidence is not None:
        payload = json.dumps(evidence.payload, separators=(",", ":"), ensure_ascii=False)
        parts.append(f"{CONTEXT_HEADER}\n{payload}")
    if not parts:
        return question
    return "\n\n".join([*parts, f"Question: {question}"])


def clean_answer(text: str) -> str:
    """Citation markers and bold removed, code identifiers turned into app labels."""
    return humanize_identifiers(_BOLD_RE.sub("", _CITATION_RE.sub("", text))).strip()


class AskService:
    def __init__(
        self,
        backboard: Backboard | None,
        assistant_id: str | None,
        allowed: frozenset[float],
        *,
        llm_provider: str | None = None,
        model_name: str | None = None,
        daily_budget: int = 300,
        per_client_daily: int = DEFAULT_PER_CLIENT_DAILY,
        thread_tokens: ThreadTokens | None = None,
        memory_tokens: MemoryTokens | None = None,
        timeout_s: float = TIMEOUT_S,
    ) -> None:
        self._backboard = backboard
        self._assistant_id = assistant_id
        self._allowed = allowed
        self._provider = llm_provider or None
        self._model = model_name or None
        self._budget = DailyBudget(daily_budget)
        self._per_client = ClientDailyLimit(per_client_daily)
        self._tokens = thread_tokens or ThreadTokens.random()
        self._memory_tokens = memory_tokens or MemoryTokens.random()
        self._timeout = timeout_s

    @property
    def enabled(self) -> bool:
        return self._backboard is not None and bool(self._assistant_id)

    def _fallback(self, thread_id: str | None, assistant_id: str, memory: MemoryState) -> AskAnswer:
        token = self._tokens.issue(thread_id, assistant_id) if thread_id else None
        return AskAnswer(FALLBACK_TEXT, token, "fallback", FALLBACK_NOTE, memory=memory)

    def ensure_enabled(self) -> None:
        if not self.enabled:
            raise AppError("ASK_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503)

    async def ask(
        self,
        question: str,
        thread_token: str | None,
        *,
        client: str,
        evidence: Evidence | None = None,
        memory_token: str | None = None,
    ) -> AskAnswer:
        """Answer from the docs and the server-built `evidence` (never free text).

        `thread_token` is the client's signed token and `client` its rate-limit key. A valid
        `memory_token` routes the question to the visitor's private clone with memory on.
        """
        if self._backboard is None or not self._assistant_id:
            raise AppError("ASK_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503)
        if not self._per_client.take(client):  # before the shared budget is spent
            raise AppError("ASK_CLIENT_LIMIT", CLIENT_LIMIT_MESSAGE, 429)
        clone = verified_clone(self._memory_tokens, memory_token, self._assistant_id)
        assistant = clone or self._assistant_id
        state: MemoryState = "on" if clone else "off"
        # Memory is written only from plain questions (where people state preferences): a turn
        # carrying street, route or area context reads memory but never writes it.
        writes = clone is not None and (evidence is None or evidence.kind == "conditions")
        mode: MemoryMode = "Auto" if writes else "Readonly"
        thread_id = self._tokens.verify(thread_token, assistant)  # unverified: a new thread
        if thread_token and thread_id is None:
            log.info("ask thread token did not verify; starting a new thread")
        if not self._budget.take():
            log.warning("ask daily budget spent; answering with the fallback")
            return self._fallback(thread_id, assistant, state)
        content = compose_content(question, evidence, memory_on=writes)
        deadline = time.monotonic() + self._timeout  # the repair shares this timeout
        try:
            raw, thread = await asyncio.wait_for(
                self._converse(self._backboard, assistant, content, thread_id, mode, self._timeout),
                timeout=self._timeout,
            )
        except ASK_ERRORS as exc:
            log.warning("ask backboard unavailable: %s", type(exc).__name__)
            return self._fallback(None, assistant, state)  # a fresh thread next time
        text, errors = self._check(raw, evidence, question)
        sources = corpus_sources(raw)
        if errors:
            log.warning("ask answer withheld by validator: %s", list(error_kinds(errors)))
            request = repair_request(text, errors)
            fixed = await self._repair(self._backboard, assistant, thread, request, deadline)
            if fixed is None:
                return self._fallback(thread, assistant, state)
            fixed_raw, thread = fixed
            text, errors = self._check(fixed_raw, evidence, question)
            if errors:
                log.warning("ask rewrite withheld by validator: %s", list(error_kinds(errors)))
                return self._fallback(thread, assistant, state)
            log.info("ask answer shown after one rewrite")
            sources = corpus_sources(fixed_raw) or sources  # the rewrite keeps the same facts
        token = self._tokens.issue(thread, assistant)
        return AskAnswer(text, token, "backboard", ASK_NOTE, sources, state)

    def _check(self, raw: str, evidence: Evidence | None, question: str) -> tuple[str, list[str]]:
        """The cleaned answer text and why it may not be shown (empty when it may)."""
        text = clean_answer(raw)
        return text, ask_validation_errors(
            text, self._allowed, evidence=evidence, question=question
        )

    async def _repair(
        self, backboard: Backboard, assistant_id: str, thread: str, request: str, deadline: float
    ) -> tuple[str, str] | None:
        """One rewrite in the same thread, memory read-only, within what is left of the timeout.

        Spends no per-client or daily budget: it finishes the question already paid for.
        """
        remaining = deadline - time.monotonic()
        if remaining < MIN_REPAIR_S:
            log.warning("ask rewrite skipped: not enough time left")
            return None
        try:
            return await asyncio.wait_for(
                self._converse(backboard, assistant_id, request, thread, "Readonly", remaining),
                timeout=remaining,
            )
        except ASK_ERRORS as exc:
            log.warning("ask rewrite unavailable: %s", type(exc).__name__)
            return None

    async def _converse(
        self,
        backboard: Backboard,
        assistant_id: str,
        content: str,
        thread_id: str | None,
        memory: MemoryMode,
        timeout: float,
    ) -> tuple[str, str]:
        """The raw reply (citation markers kept, for sources) and the canonical thread id."""
        thread = thread_id or _canonical(await backboard.create_thread(assistant_id, timeout))
        reply = await backboard.send_message(
            thread_id=thread,
            assistant_id=assistant_id,
            content=content,
            memory=memory,  # "Readonly" on the shared assistant; "Auto" only on a clone
            llm_provider=self._provider,
            model_name=self._model,
            timeout=timeout,
        )
        if reply.status != COMPLETED:
            raise BackboardError("run not completed")
        return reply.content, _canonical(reply.thread_id)


def _canonical(raw: str) -> str:
    """Backboard thread ids must be UUIDs, or the next call could not send them back."""
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise BackboardError("thread id is not a UUID") from None
