"""City Pulse area detail: citywide area traffic-risk scores (CITY-01..04).

Shared by the /areas endpoints and Ask PathPro's area context, so the API layer never imports
another API module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.api.envelope import AppError
from app.api.schemas import ConditionUsed, FactorOut
from app.domain.scoring import attribute, band_for
from app.domain.timeutil import cell_at, parse_departure
from app.repositories.artifacts import Bundle
from app.repositories.hexes import HexBundle
from app.services.weather import Resolved, WeatherService

TOP_FACTORS = 4


class AreaDetail(BaseModel):
    cell: str
    lat: float
    lon: float
    score: int
    band: str
    confidence: Literal["high", "medium", "limited"]
    baseline_points: int
    factors: list[FactorOut]
    remainder_points: int
    crashes: float
    ped_crashes: float
    period: str
    in_street_coverage: bool
    condition_used: ConditionUsed
    at: str


def condition_used(resolved: Resolved) -> ConditionUsed:
    return ConditionUsed(
        cond="wet" if resolved.wet else "dry",
        source=resolved.source,  # type: ignore[arg-type]
        label=resolved.label,
    )


def parse_time(t: str) -> datetime:
    """The departure time, or a BAD_TIME error the client can show."""
    try:
        return parse_departure(t)
    except ValueError as exc:
        raise AppError("BAD_TIME", "Pick a valid time.", 422) from exc


def require_hexes(hexes: HexBundle | None) -> HexBundle:
    if hexes is None:
        raise AppError("CITY_PULSE_UNAVAILABLE", "Citywide area scores are not available.", 503)
    return hexes


def area_detail(
    hexes: HexBundle, bundle: Bundle, cell: str, at: datetime, wet: bool, used: ConditionUsed
) -> AreaDetail:
    i = hexes.index[cell]
    factors = {k: float(v) for k, v in zip(hexes.factor_keys, hexes.factors[i], strict=True)}
    factors[hexes.temporal_key] = hexes.temporal_log(i, cell_at(at, wet))
    result = attribute(hexes.base, factors, hexes.quantiles, top_n=TOP_FACTORS)
    lat, lon = float(hexes.lat[i]), float(hexes.lon[i])
    west, south, east, north = bundle.manifest["coverage_bbox"]
    return AreaDetail(
        cell=cell,
        lat=lat,
        lon=lon,
        score=result.score,
        band=band_for(result.score).value,
        confidence=hexes.confidence[i],  # type: ignore[arg-type]
        baseline_points=result.baseline_points,
        factors=[
            FactorOut(key=f.key, label=hexes.labels[f.key], points=f.points) for f in result.factors
        ],
        remainder_points=result.remainder_points,
        crashes=float(hexes.crashes[i]),
        ped_crashes=float(hexes.ped_crashes[i]),
        period="2020-2024",
        in_street_coverage=west <= lon <= east and south <= lat <= north,
        condition_used=used,
        at=at.isoformat(),
    )


async def resolve_area_detail(
    hexes: HexBundle | None,
    bundle: Bundle,
    weather: WeatherService,
    cell: str | None,
    t: str,
    cond: str,
) -> AreaDetail:
    """One area's detail at a time and condition; raises the /areas error codes."""
    city = require_hexes(hexes)
    if cell is None or cell not in city.index:
        raise AppError("OUTSIDE_CITY", "City Pulse covers the City of Atlanta.", 404)
    at = parse_time(t)
    resolved = await weather.resolve(cond, at)
    return area_detail(city, bundle, cell, at, resolved.wet, condition_used(resolved))
