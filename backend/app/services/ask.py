"""Ask PathPro: questions about PathPro itself, answered by a Backboard assistant from its docs.

Privacy and trust rules:
- Public users can never write the shared assistant's memory: every message uses
  memory="Readonly". Thread ids are opaque UUIDs held only in the asker's browser tab.
- The answer is shown only if it passes the explanation validator's Ask rules (banned words,
  crime framing, every number found in the docs corpus). Anything else, and any upstream error,
  timeout, or spent daily budget, returns a fixed fallback that points to the model card; the
  raw LLM text is never shown or logged. Logs carry exception type names only.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Literal

import httpx

from app.api.envelope import AppError
from app.services.backboard import Backboard, BackboardError
from app.services.explain.service import DailyBudget
from app.services.explain.validator import ask_validation_errors

log = logging.getLogger(__name__)

TIMEOUT_S = 12.0
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
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# Retrieval citation markers such as 【4:0†model_card.md】 or [2] are not part of the answer.
_CITATION_RE = re.compile(r"【[^】]*】|\[\d{1,3}\]")
_BOLD_RE = re.compile(r"\*\*|__")
ASK_ERRORS = (httpx.HTTPError, BackboardError, TimeoutError)
Source = Literal["backboard", "fallback"]


@dataclass(frozen=True)
class AskAnswer:
    text: str
    thread_id: str | None
    source: Source
    sources_note: str


def clean_question(raw: str) -> str:
    """Trimmed question text; 3-300 characters with no control characters."""
    question = raw.strip()
    if _CONTROL_RE.search(question):
        raise AppError("BAD_QUESTION", "Please ask on a single line of plain text.", 422)
    if not MIN_QUESTION_CHARS <= len(question) <= MAX_QUESTION_CHARS:
        raise AppError("BAD_QUESTION", "Questions need 3 to 300 characters.", 422)
    return question


def parse_thread_id(raw: str | None) -> str | None:
    """A canonical UUID string, or None to start a new thread."""
    if raw is None:
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise AppError("BAD_THREAD", "That conversation id is not valid.", 422) from None


def clean_answer(text: str) -> str:
    return _BOLD_RE.sub("", _CITATION_RE.sub("", text)).strip()


def _fallback(thread_id: str | None) -> AskAnswer:
    return AskAnswer(FALLBACK_TEXT, thread_id, "fallback", FALLBACK_NOTE)


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
        timeout_s: float = TIMEOUT_S,
    ) -> None:
        self._backboard = backboard
        self._assistant_id = assistant_id
        self._allowed = allowed
        self._provider = llm_provider or None
        self._model = model_name or None
        self._budget = DailyBudget(daily_budget)
        self._timeout = timeout_s

    @property
    def enabled(self) -> bool:
        return self._backboard is not None and bool(self._assistant_id)

    async def ask(self, question: str, thread_id: str | None) -> AskAnswer:
        if self._backboard is None or not self._assistant_id:
            raise AppError("ASK_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503)
        if not self._budget.take():
            log.warning("ask daily budget spent; answering with the fallback")
            return _fallback(thread_id)
        try:
            text, thread = await asyncio.wait_for(
                self._converse(self._backboard, self._assistant_id, question, thread_id),
                timeout=self._timeout,
            )
        except ASK_ERRORS as exc:
            log.warning("ask backboard unavailable: %s", type(exc).__name__)
            return _fallback(None)  # the client starts a fresh thread next time
        errors = ask_validation_errors(text, self._allowed)
        if errors:
            kinds = sorted({e.split(":", 1)[0] for e in errors})
            log.warning("ask answer withheld by validator: %s", kinds)
            return _fallback(thread)
        return AskAnswer(text, thread, "backboard", ASK_NOTE)

    async def _converse(
        self, backboard: Backboard, assistant_id: str, question: str, thread_id: str | None
    ) -> tuple[str, str]:
        thread = thread_id or _canonical(await backboard.create_thread(assistant_id, self._timeout))
        reply = await backboard.send_message(
            thread_id=thread,
            assistant_id=assistant_id,
            content=question,
            memory="Readonly",  # public users never write shared assistant memory
            llm_provider=self._provider,
            model_name=self._model,
            timeout=self._timeout,
        )
        if reply.status != COMPLETED:
            raise BackboardError("run not completed")
        return clean_answer(reply.content), _canonical(reply.thread_id)


def _canonical(raw: str) -> str:
    """Backboard thread ids must be UUIDs, or the next call could not send them back."""
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise BackboardError("thread id is not a UUID") from None
