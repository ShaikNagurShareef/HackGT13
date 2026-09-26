"""Request and response schemas (separate models per ECC FastAPI rules)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.modes import ModeKey, Network
from app.domain.reports import ReportCategory

Condition = Literal["live", "dry", "wet"]
Preference = Literal["lower_traffic_risk", "lit_and_busy"]


class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    depart_at: str = Field(default="now", max_length=40)
    cond: Condition = "live"
    prefer: Preference = "lower_traffic_risk"  # lit_and_busy only changes walks after dark
    mode: ModeKey = "walk"  # bike / ebike / scooter plan on the ride network


class ConditionUsed(BaseModel):
    cond: Literal["dry", "wet"]
    source: Literal["live", "override", "assumed"]
    label: str


class NamedSegmentOut(BaseModel):
    seg_id: int
    name: str
    score: int


class AlertOut(BaseModel):
    start_m: float
    end_m: float
    names: list[str]
    score: int
    stretches: int


class RouteSafetyOut(BaseModel):
    """Signals along a route. busy_share = moderate-or-busy share of known foot traffic;
    help points within 100 m; crimes are context only and never shape the route."""

    lit_share: float | None = Field(ge=0, le=1)
    busy_share: float | None = Field(ge=0, le=1)
    help_points_within_100m: int = Field(ge=0)
    crimes_persons_nearby: int = Field(ge=0)
    day_part: Literal["night", "morning", "afternoon", "evening"]


class RouteOut(BaseModel):
    coords: list[list[float]]
    duration_s: float
    distance_m: float
    risk_score: int
    band: str
    exposure: float
    high_risk_m: float
    limited_data_m: float
    segment_ids: list[int]
    top_segments: list[NamedSegmentOut]
    alerts: list[AlertOut] = []
    safety: RouteSafetyOut | None = None  # None without a safety layer, and for ride modes


class ReportRequest(BaseModel):
    """Only a segment and a fixed category: location comes from the segment, never the client."""

    model_config = ConfigDict(extra="forbid")

    seg_id: int = Field(ge=0)
    category: ReportCategory


class ReportOut(BaseModel):
    seg_id: int
    category: ReportCategory
    label: str
    street: str
    lon: float
    lat: float
    confirmations: int
    updated_at: datetime
    expires_at: datetime


class ReportSummaryOut(BaseModel):
    category: ReportCategory
    label: str
    reports: int
    confirmations: int


class RoutesData(BaseModel):
    condition_used: ConditionUsed
    depart_at: str
    fastest: RouteOut
    pathpro: RouteOut | None
    message_code: str
    message: str | None
    time_cost_min: float | None
    exposure_reduction_pct: int | None
    unavoidable: list[str]
    avoided: list[NamedSegmentOut] = []
    route_key: str
    reports: list[ReportOut] = []  # community context only; never part of scores or evidence
    mode: ModeKey = "walk"
    prefer: Preference = "lower_traffic_risk"  # the preference actually used (walk only)


class FactorOut(BaseModel):
    key: str
    label: str
    points: int


class HistoryOut(BaseModel):
    crashes: float
    ped_crashes: float
    dark_share: float
    wet_share: float
    period: str


class SegmentDetail(BaseModel):
    seg_id: int
    name: str
    road_group: str
    score: int
    band: str
    confidence: Literal["high", "medium", "limited"]
    baseline_points: int
    factors: list[FactorOut]
    remainder_points: int
    history: HistoryOut
    condition_used: ConditionUsed
    at: str
    mode: ModeKey = "walk"  # ride-mode segment ids index the ride model


class ModeOut(BaseModel):
    key: ModeKey
    label: str
    available: bool
    speed_kmh: float
    network: Network
    static_prefix: Literal["", "ride_"]


class MetaData(BaseModel):
    model_version: str
    data_through: str
    n_segments: int
    coverage_bbox: list[float]
    day_groups: list[str]
    conditions: list[str]
    reference_dates: dict[str, str]
    frame_light: dict[str, list[str]]
    static_base: str
    headline: dict[str, object]
    spatial_factors: list[FactorOut]
    temporal_factors: list[FactorOut]
    modes: list[ModeOut] = []
    ride_model: dict[str, object] | None = None  # the ride model's headline metrics


class ModesHealth(BaseModel):
    walk: Literal["ok"] = "ok"
    ride: Literal["ok", "unavailable"] = "unavailable"


class HealthData(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: str
    segments: int
    graph_nodes: int
    database: Literal["ok", "unavailable", "not_configured"]
    reports: Literal["ok", "unavailable", "not_configured"] = "not_configured"
    safety: Literal["ok", "unavailable"] = "unavailable"
    modes: ModesHealth = Field(default_factory=ModesHealth)


class StationOut(BaseModel):
    name: str
    lat: float
    lon: float
    lines: list[str] = []
