"""Share-my-walk request and response schemas (separate models; no token or hash in responses)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.walks import MAX_ETA_S, MAX_LABEL_CHARS, MAX_ROUTE_POINTS, WalkStatus

Lat = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Lon = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LABEL_CHARS)
]
OwnerToken = Annotated[str, StringConstraints(min_length=16, max_length=128)]
EtaS = Annotated[int, Field(ge=0, le=MAX_ETA_S)]


class DestinationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Label
    lat: Lat
    lon: Lon


class CreateWalkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: DestinationIn
    eta_s: EtaS
    route: list[tuple[Lon, Lat]] | None = Field(default=None, max_length=MAX_ROUTE_POINTS)


class PositionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_token: OwnerToken
    lat: Lat
    lon: Lon
    accuracy_m: float | None = Field(default=None, ge=0, le=10_000, allow_inf_nan=False)
    eta_s: EtaS | None = None
    status: WalkStatus | None = None


class CreatedWalkOut(BaseModel):
    walk_id: str
    owner_token: str  # returned once, at creation; only its SHA-256 is stored
    follow_path: str
    expires_at: datetime


class DestinationOut(BaseModel):
    label: str
    lat: float
    lon: float


class PositionOut(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None
    at: datetime


class WalkSummaryOut(BaseModel):
    walk_id: str
    status: WalkStatus
    destination: DestinationOut
    eta_s: int
    eta_at: datetime
    position: PositionOut | None
    updated_at: datetime
    expires_at: datetime


class WalkOut(WalkSummaryOut):
    route: list[tuple[float, float]] | None
