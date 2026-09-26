"""Request and response schemas (separate models per ECC FastAPI rules)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Condition = Literal["live", "dry", "wet"]


class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    depart_at: str = Field(default="now", max_length=40)
    cond: Condition = "live"


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


class RoutesData(BaseModel):
    condition_used: ConditionUsed
    depart_at: str
    fastest: RouteOut
    pathpulse: RouteOut | None
    message_code: str
    message: str | None
    time_cost_min: float | None
    exposure_reduction_pct: int | None
    unavoidable: list[str]
    avoided: list[NamedSegmentOut] = []
    route_key: str


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


class HealthData(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: str
    segments: int
    graph_nodes: int
    database: Literal["ok", "unavailable", "not_configured"]
