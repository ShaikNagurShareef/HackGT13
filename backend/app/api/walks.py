"""Share my walk: a walker shares a follow link; a friend sees live position, destination, ETA."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from app.api.deps import get_bundle
from app.api.envelope import Envelope, ok
from app.api.walk_schemas import (
    CreatedWalkOut,
    CreateWalkRequest,
    PositionUpdateRequest,
    WalkOut,
    WalkSummaryOut,
)
from app.repositories.artifacts import Bundle
from app.repositories.walks import WalksRepository
from app.services.walks import (
    Clock,
    RecentUpdates,
    create_walk,
    get_walk,
    unavailable,
    update_position,
    utcnow,
)

walks = APIRouter()
BundleDep = Annotated[Bundle, Depends(get_bundle)]
MAX_WALK_ID_CHARS = 128  # longer ids are refused before any lookup


def get_walks(request: Request) -> WalksRepository:
    repo: WalksRepository = request.app.state.walks
    if not repo.configured:
        raise unavailable()
    return repo


def get_clock() -> Clock:
    return utcnow


def get_update_gate(request: Request) -> RecentUpdates:
    gate: RecentUpdates = request.app.state.walk_gate
    return gate


WalksDep = Annotated[WalksRepository, Depends(get_walks)]
GateDep = Annotated[RecentUpdates, Depends(get_update_gate)]
ClockDep = Annotated[Clock, Depends(get_clock)]
WalkId = Annotated[str, Path(max_length=MAX_WALK_ID_CHARS)]


@walks.post("/walks", response_model=Envelope[CreatedWalkOut], status_code=201)
async def start_shared_walk(
    req: CreateWalkRequest, repo: WalksDep, clock: ClockDep, bundle: BundleDep
) -> Envelope[CreatedWalkOut]:
    """Start sharing: returns the follow path and a one-time owner token for position updates."""
    return ok(await create_walk(repo, req, clock()), bundle.model_version)


@walks.put("/walks/{walk_id}/position", response_model=Envelope[WalkSummaryOut])
async def post_position(
    walk_id: WalkId,
    req: PositionUpdateRequest,
    repo: WalksDep,
    clock: ClockDep,
    bundle: BundleDep,
    gate: GateDep,
) -> Envelope[WalkSummaryOut]:
    """Owner-only: the walker's latest position, ETA, and status."""
    return ok(await update_position(repo, walk_id, req, clock(), gate), bundle.model_version)


@walks.get("/walks/{walk_id}", response_model=Envelope[WalkOut])
async def follow_walk(
    walk_id: WalkId, repo: WalksDep, clock: ClockDep, bundle: BundleDep
) -> Envelope[WalkOut]:
    """What a follower sees. Never includes the owner token or its hash."""
    return ok(await get_walk(repo, walk_id, clock()), bundle.model_version)
