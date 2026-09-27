"""POST /ask: Ask PathPro about itself and what is on screen (Backboard, validated answers)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.ask_context import AskContext, ContextUsed, resolve_ask_context
from app.api.envelope import Envelope, ok
from app.middleware import client_key
from app.services.ask import AskService, MemoryState, clean_question

ask = APIRouter()
# Generous transport caps; the service applies the real 3-300 character rule and verifies the
# signed thread token (an unverified token starts a new conversation, never an error).
MAX_RAW_QUESTION = 1000
MAX_RAW_THREAD = 128


class AskRequest(BaseModel):
    """The question, an optional signed thread token, and what is on screen (ids only)."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(max_length=MAX_RAW_QUESTION)
    thread_id: str | None = Field(default=None, max_length=MAX_RAW_THREAD)
    context: AskContext | None = None


class AskSourceOut(BaseModel):
    label: str
    url: str


class AskData(BaseModel):
    answer: str
    thread_id: str | None  # signed token "<uuid>.<sig>", opaque to the browser
    source: Literal["backboard", "fallback"]
    note: str
    sources: list[AskSourceOut]
    memory: MemoryState
    context_used: ContextUsed
    context_dropped: bool


@ask.post("/ask", response_model=Envelope[AskData])
async def ask_pathpro(req: AskRequest, request: Request) -> Envelope[AskData]:
    question = clean_question(req.question)
    service: AskService = request.app.state.ask
    service.ensure_enabled()
    context = await resolve_ask_context(request, req.context)
    client = client_key(request.client.host if request.client else None)
    answer = await service.ask(question, req.thread_id, client=client, evidence=context.evidence)
    data = AskData(
        answer=answer.text,
        thread_id=answer.thread_id,
        source=answer.source,
        note=answer.sources_note,
        sources=[AskSourceOut(label=s.label, url=s.url) for s in answer.sources],
        memory=answer.memory,
        context_used=context.used,
        context_dropped=context.dropped,
    )
    return ok(data, request.app.state.bundle.model_version)
