"""Minimal Backboard REST client (https://app.backboard.io/api), shared by Ask PathPro and setup.

Only the calls PathPro needs. Responses are parsed strictly: anything unexpected raises
BackboardError, never a guess. The API key rides in the X-API-Key header and is never logged
or included in an error message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

BACKBOARD_API = "https://app.backboard.io/api"
DEFAULT_TIMEOUT_S = 12.0
UPLOAD_TIMEOUT_S = 60.0
MemoryMode = Literal["Auto", "Readonly", "off"]


class BackboardError(ValueError):
    """Backboard answered, but not with the shape PathPro expects."""


@dataclass(frozen=True)
class Reply:
    content: str
    thread_id: str
    status: str


def _object(resp: httpx.Response) -> dict[str, Any]:
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as exc:
        raise BackboardError("response is not JSON") from exc
    if not isinstance(data, dict):
        raise BackboardError("response is not an object")
    return data


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise BackboardError(f"missing {key}")
    return value


@dataclass(frozen=True)
class Backboard:
    client: httpx.AsyncClient
    api_key: str = field(repr=False)
    base_url: str = BACKBOARD_API

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    async def _post(self, path: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        resp = await self.client.post(
            f"{self.base_url}{path}", json=body, headers=self._headers, timeout=timeout
        )
        return _object(resp)

    async def create_assistant(self, name: str, system_prompt: str, tok_k: int) -> str:
        body = {"name": name, "system_prompt": system_prompt, "tok_k": tok_k}
        return _text(await self._post("/assistants", body, DEFAULT_TIMEOUT_S), "assistant_id")

    async def upload_document(self, assistant_id: str, filename: str, content: bytes) -> str:
        """Upload one file for the assistant's retrieval index; returns its document id."""
        resp = await self.client.post(
            f"{self.base_url}/assistants/{assistant_id}/documents",
            files={"file": (filename, content)},
            headers=self._headers,
            timeout=UPLOAD_TIMEOUT_S,
        )
        return _text(_object(resp), "document_id")

    async def document_status(self, document_id: str) -> str:
        resp = await self.client.get(
            f"{self.base_url}/documents/{document_id}/status",
            headers=self._headers,
            timeout=DEFAULT_TIMEOUT_S,
        )
        return _text(_object(resp), "status")

    async def add_memory(self, assistant_id: str, content: str) -> None:
        await self._post(
            f"/assistants/{assistant_id}/memories", {"content": content}, DEFAULT_TIMEOUT_S
        )

    async def create_thread(self, assistant_id: str, timeout: float = DEFAULT_TIMEOUT_S) -> str:
        data = await self._post(f"/assistants/{assistant_id}/threads", {}, timeout)
        return _text(data, "thread_id")

    async def send_message(
        self,
        *,
        thread_id: str,
        assistant_id: str,
        content: str,
        memory: MemoryMode,
        llm_provider: str | None,
        model_name: str | None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> Reply:
        body: dict[str, Any] = {
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "content": content,
            "memory": memory,
            "stream": False,
            "send_to_llm": "true",
        }
        if llm_provider and model_name:
            body = {**body, "llm_provider": llm_provider, "model_name": model_name}
        data = await self._post("/threads/messages", body, timeout)
        return Reply(
            content=_text(data, "content"),
            thread_id=_text(data, "thread_id"),
            status=_text(data, "status"),
        )
