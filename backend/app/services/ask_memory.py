"""Ask PathPro opt-in private memory: one Backboard assistant clone per browser.

Turning memory on clones the shared docs assistant (documents and read-only facts included)
into a private assistant and returns a signed memory token for it; the browser keeps only the
token. Asking with a valid token uses the clone with memory="Auto", so what the visitor states
(their usual travel times, preferences) carries across conversations. The clone's fact
extraction prompt, set on the base assistant by `app.tools.setup_backboard`, keeps stated
preferences only; never places, streets, routes, or the per-question context block.

"Forget me" deletes the clone and everything it remembered. Forgetting is idempotent and never
reveals whether a token was valid: an unverified token is simply a no-op. Clones cost upstream
resources, so each client may create a few per day, under a shared daily cap. Logs carry
exception type names only; never tokens, clone ids, or anything the visitor typed.
"""

from __future__ import annotations

import logging
import secrets
import uuid

import httpx

from app.api.envelope import AppError
from app.services.ask_threads import MemoryTokens
from app.services.backboard import Backboard, BackboardError
from app.services.explain.service import DailyBudget
from app.services.limits import ClientDailyLimit

log = logging.getLogger(__name__)

ASK_MEMORY_PER_CLIENT_DAILY = 3
DEFAULT_MEMORY_DAILY = 100
CLONE_PREFIX = "pathpro-visitor-"
CLONE_SUFFIX_BYTES = 6  # 12 hex characters
NOT_FOUND = 404
UNAVAILABLE_MESSAGE = "Ask PathPro is unavailable right now. About PathPro has the model card."
LIMIT_MESSAGE = "Memory can't be turned on again today. Ask PathPro still works without it."
FAILED_MESSAGE = "Memory couldn't be turned on right now. Ask PathPro still works without it."
FORGET_FAILED_MESSAGE = "Couldn't forget your Ask PathPro memory right now. Please try again."
MEMORY_ERRORS = (httpx.HTTPError, BackboardError, ValueError)


def clone_name() -> str:
    return f"{CLONE_PREFIX}{secrets.token_hex(CLONE_SUFFIX_BYTES)}"


def verified_clone(tokens: MemoryTokens, token: str | None, base: str | None) -> str | None:
    """The visitor's clone for a valid memory token; never the shared base assistant."""
    clone = tokens.verify(token)
    if clone is None or not base or _same_id(clone, base):
        return None
    return clone


class AskMemory:
    def __init__(
        self,
        backboard: Backboard | None,
        base_assistant_id: str | None,
        tokens: MemoryTokens,
        *,
        daily_budget: int = DEFAULT_MEMORY_DAILY,
        per_client_daily: int = ASK_MEMORY_PER_CLIENT_DAILY,
    ) -> None:
        self._backboard = backboard
        self._base = base_assistant_id
        self._tokens = tokens
        self._budget = DailyBudget(daily_budget)
        self._per_client = ClientDailyLimit(per_client_daily)

    def _require(self) -> tuple[Backboard, str]:
        if self._backboard is None or not self._base:
            raise AppError("ASK_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503)
        return self._backboard, self._base

    async def enable(self, client: str) -> str:
        """Clone the base assistant for this visitor; returns the signed memory token."""
        backboard, base = self._require()
        if not self._per_client.take(client) or not self._budget.take():
            raise AppError("ASK_MEMORY_LIMIT", LIMIT_MESSAGE, 429)
        try:
            clone = _canonical(await backboard.clone_assistant(base, clone_name()))
        except MEMORY_ERRORS as exc:
            log.warning("ask memory clone failed: %s", type(exc).__name__)
            raise AppError("ASK_MEMORY_FAILED", FAILED_MESSAGE, 502) from None
        if _same_id(clone, base):
            log.warning("ask memory clone returned the base assistant")
            raise AppError("ASK_MEMORY_FAILED", FAILED_MESSAGE, 502)
        return self._tokens.issue(clone)

    async def forget(self, token: str) -> None:
        """Delete the visitor's clone; an unverified token is a silent no-op."""
        backboard, _ = self._require()
        clone = verified_clone(self._tokens, token, self._base)
        if clone is None:
            return
        try:
            await backboard.delete_assistant(clone)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == NOT_FOUND:
                return  # already gone: forgetting is idempotent
            log.warning("ask memory forget failed: %s", type(exc).__name__)
            raise AppError("ASK_MEMORY_FORGET_FAILED", FORGET_FAILED_MESSAGE, 502) from None
        except httpx.HTTPError as exc:
            log.warning("ask memory forget failed: %s", type(exc).__name__)
            raise AppError("ASK_MEMORY_FORGET_FAILED", FORGET_FAILED_MESSAGE, 502) from None


def _same_id(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def _canonical(raw: str) -> str:
    """Assistant ids must be UUIDs to be signed; anything else is an upstream error."""
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise BackboardError("assistant id is not a UUID") from None
