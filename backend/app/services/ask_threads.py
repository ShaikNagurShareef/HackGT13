"""Signed Ask PathPro tokens: the browser never holds a bare Backboard id.

A token is "<uuid>.<sig>" where sig is the URL-safe base64 HMAC-SHA256, under a server secret,
of a purpose, an optional binding, and the canonical UUID. Only tokens this server issued
verify, so a client cannot continue a conversation or use a memory clone by guessing or copying
someone else's Backboard id. Two purposes share the secret without being interchangeable:

- ThreadTokens sign a Backboard thread id bound to the assistant it belongs to, so a thread
  from the shared assistant cannot be continued on a memory clone, or the reverse.
- MemoryTokens sign a visitor's private memory clone (an assistant id).

Without a configured secret each process draws a random one at startup; tokens from before a
restart then simply fail to verify and the asker starts over. Tokens are never logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from typing import ClassVar, Self

SECRET_BYTES = 32
SIG_CHARS = 32  # 192 bits of the 256-bit MAC, URL-safe base64 without padding
_TOKEN_RE = re.compile(r"^([0-9a-f-]{36})\.([A-Za-z0-9_-]{22,64})$")
_SEPARATOR = "\x1f"  # never appears in a purpose, a UUID, or an assistant id


def random_secret() -> bytes:
    return secrets.token_bytes(SECRET_BYTES)


class SignedIds:
    PURPOSE: ClassVar[str] = "ask"

    def __init__(self, secret: bytes) -> None:
        if not secret:
            raise ValueError("token secret must not be empty")
        self._secret = secret

    @classmethod
    def random(cls) -> Self:
        """A per-process secret; tokens stop verifying after a restart."""
        return cls(random_secret())

    def _sign(self, value: str, bound: str) -> str:
        message = _SEPARATOR.join((self.PURPOSE, bound, value)).encode("utf-8")
        mac = hmac.new(self._secret, message, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")[:SIG_CHARS]

    def issue(self, value: str, bound: str = "") -> str:
        """The opaque token for a Backboard UUID (canonicalized first), bound to `bound`."""
        canonical = str(uuid.UUID(value))
        return f"{canonical}.{self._sign(canonical, bound)}"

    def verify(self, token: str | None, bound: str = "") -> str | None:
        """The Backboard UUID when this server issued the token for `bound`; otherwise None."""
        if not token:
            return None
        match = _TOKEN_RE.match(token)
        if match is None:
            return None
        value, sig = match.groups()
        try:
            canonical = str(uuid.UUID(value))
        except ValueError:
            return None
        if canonical != value:
            return None
        expected = self._sign(canonical, bound).encode("ascii")
        if not hmac.compare_digest(sig.encode("ascii"), expected):
            return None
        return canonical


class ThreadTokens(SignedIds):
    """Backboard thread ids, bound to their assistant id."""

    PURPOSE = "ask-thread"


class MemoryTokens(SignedIds):
    """A visitor's private Backboard memory clone (an assistant id)."""

    PURPOSE = "ask-memory"
