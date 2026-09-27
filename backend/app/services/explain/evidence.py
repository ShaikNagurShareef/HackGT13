"""Structured evidence for explanations: the only input the LLM ever sees (GEN-01)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.api.schemas import FactorOut, RoutesData, SegmentDetail
from app.domain.timeutil import ATLANTA, light_at
from app.services.areas import AreaDetail
from app.services.weather import Resolved

MAX_FACTORS = 3
_TEXT_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Evidence:
    kind: str  # "segment" | "route" | "area" | "conditions"
    payload: dict[str, Any]
    numbers: frozenset[float] = field(default_factory=frozenset)


def _collect_numbers(value: Any, out: set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        out.add(round(float(value), 1))
    elif isinstance(value, str):
        # Numbers inside evidence text (the "2020-2024" period) may be reworded freely.
        out.update(round(float(n), 1) for n in _TEXT_NUMBER_RE.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            _collect_numbers(v, out)
    elif isinstance(value, list | tuple):
        for v in value:
            _collect_numbers(v, out)


# Street names come from OpenStreetMap (anyone can edit it), so every string that reaches an
# LLM is flattened to one short line: no control characters, newlines, or long instructions.
MAX_LABEL_CHARS = 80
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_SPACE_RE = re.compile(r"\s+")


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        flat = _SPACE_RE.sub(" ", _CONTROL_RE.sub(" ", value)).strip()
        return flat[:MAX_LABEL_CHARS].rstrip()
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    return value


def _with_numbers(kind: str, payload: dict[str, Any]) -> Evidence:
    clean = _clean(payload)
    nums: set[float] = set()
    _collect_numbers(clean, nums)
    return Evidence(kind=kind, payload=clean, numbers=frozenset(nums))


def _time_label(iso: str) -> str:

    ts = datetime.fromisoformat(iso).astimezone(ATLANTA)
    hour12 = ts.hour % 12 or 12
    return f"{hour12} {'AM' if ts.hour < 12 else 'PM'}"


def _involving(detail: SegmentDetail) -> dict[str, int]:
    """Crashes involving this mode's travellers: pedestrians for walk, bikes for ride."""
    if detail.mode == "walk":
        return {"pedestrian_crashes": round(detail.history.ped_crashes)}
    if detail.history.bike_crashes is not None:
        return {"bike_crashes": round(detail.history.bike_crashes)}
    return {}


def _factor_lists(factors: list[FactorOut]) -> dict[str, list[dict[str, Any]]]:
    ups = [f for f in factors if f.points > 0][:MAX_FACTORS]
    downs = [f for f in factors if f.points < 0][:1]
    return {
        "raises_risk": [{"factor": f.label, "points": f.points} for f in ups],
        "lowers_risk": [{"factor": f.label, "points": abs(f.points)} for f in downs],
    }


def segment_evidence(detail: SegmentDetail) -> Evidence:
    history = {
        "crashes": round(detail.history.crashes),
        **_involving(detail),
        "period": detail.history.period,
    }
    payload = {
        "mode": detail.mode,
        "street": detail.name,
        "score": detail.score,
        "band": detail.band,
        "time": _time_label(detail.at),
        "conditions": detail.condition_used.cond,
        "confidence": detail.confidence,
        **_factor_lists(detail.factors),
        "history": history,
    }
    return _with_numbers("segment", payload)


def route_evidence(routes: RoutesData) -> Evidence:
    fastest, pp = routes.fastest, routes.pathpro
    fast_names = [s.name for s in fastest.top_segments]
    payload: dict[str, Any] = {
        "mode": routes.mode,
        "time": _time_label(routes.depart_at),
        "conditions": routes.condition_used.cond,
        "fastest": {
            "minutes": round(fastest.duration_s / 60),
            "score": fastest.risk_score,
            "riskiest_streets": fast_names,
        },
    }
    if pp is not None:
        pp_names = {s.name for s in pp.top_segments}
        payload["pathpro"] = {
            "minutes": round(pp.duration_s / 60),
            "score": pp.risk_score,
            "extra_minutes": routes.time_cost_min,
            "less_exposure_percent": routes.exposure_reduction_pct,
            "avoids": [n for n in fast_names if n not in pp_names][:2],
        }
    else:
        payload["fastest_is_lower_risk"] = True
    if routes.unavoidable:
        payload["unavoidable"] = routes.unavoidable[:2]
    return _with_numbers("route", payload)


def area_evidence(detail: AreaDetail) -> Evidence:
    """A City Pulse area: its score and drivers; never its cell id or coordinates."""
    payload = {
        "area": "City Pulse area",
        "score": detail.score,
        "band": detail.band,
        "time": _time_label(detail.at),
        "conditions": detail.condition_used.cond,
        "confidence": detail.confidence,
        **_factor_lists(detail.factors),
        "history": {
            "crashes": round(detail.crashes),
            "pedestrian_crashes": round(detail.ped_crashes),
            "period": detail.period,
        },
    }
    return _with_numbers("area", payload)


_LIGHT_WORDS = {"day": "daylight", "twilight": "twilight", "dark": "dark"}


def conditions_evidence(resolved: Resolved, at: datetime) -> Evidence:
    """Live conditions only: day, hour, light and wetness (no place, no score)."""
    local = at.astimezone(ATLANTA)
    payload = {
        "day": local.strftime("%A"),
        "time": _time_label(local.isoformat()),
        "light": _LIGHT_WORDS[light_at(local)],
        "conditions": "wet" if resolved.wet else "dry",
    }
    return _with_numbers("conditions", payload)
