"""Signed Ask PathPro thread tokens: the browser never holds a bare Backboard thread id.

A token is "<uuid>.<sig>" where sig is the URL-safe base64 HMAC-SHA256 of the canonical UUID
under a server secret. Only tokens this server issued verify, so a client cannot continue a
conversation by guessing or copying someone else's Backboard thread id. Without a configured
secret each process draws a random one at startup; tokens from before a restart then simply
fail to verify and the asker starts a new conversation. Tokens are never logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid

SECRET_BYTES = 32
SIG_CHARS = 32  # 192 bits of the 256-bit MAC, URL-safe base64 without padding
_TOKEN_RE = re.compile(r"^([0-9a-f-]{36})\.([A-Za-z0-9_-]{22,64})$")


class ThreadTokens:
    def __init__(self, secret: bytes) -> None:
        if not secret:
            raise ValueError("thread token secret must not be empty")
        self._secret = secret

    @classmethod
    def random(cls) -> ThreadTokens:
        """A per-process secret; tokens stop verifying after a restart (a new conversation)."""
        return cls(secrets.token_bytes(SECRET_BYTES))

    def _sign(self, thread_id: str) -> str:
        mac = hmac.new(self._secret, thread_id.encode("ascii"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")[:SIG_CHARS]

    def issue(self, thread_id: str) -> str:
        """The opaque token for a Backboard thread id (canonicalized first)."""
        canonical = str(uuid.UUID(thread_id))
        return f"{canonical}.{self._sign(canonical)}"

    def verify(self, token: str | None) -> str | None:
        """The Backboard thread id when this server issued the token; otherwise None."""
        if not token:
            return None
        match = _TOKEN_RE.match(token)
        if match is None:
            return None
        thread_id, sig = match.groups()
        try:
            canonical = str(uuid.UUID(thread_id))
        except ValueError:
            return None
        if canonical != thread_id:
            return None
        if not hmac.compare_digest(sig.encode("ascii"), self._sign(canonical).encode("ascii")):
            return None
        return canonical
