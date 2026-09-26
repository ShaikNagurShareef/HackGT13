"""Structured evidence for explanations: the only input the LLM ever sees (GEN-01)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.api.schemas import RoutesData, SegmentDetail
from app.domain.timeutil import ATLANTA

MAX_FACTORS = 3
_TEXT_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Evidence:
    kind: str  # "segment" | "route"
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


def _with_numbers(kind: str, payload: dict[str, Any]) -> Evidence:
    nums: set[float] = set()
    _collect_numbers(payload, nums)
    return Evidence(kind=kind, payload=payload, numbers=frozenset(nums))


def _time_label(iso: str) -> str:
    from datetime import datetime

    ts = datetime.fromisoformat(iso).astimezone(ATLANTA)
    hour12 = ts.hour % 12 or 12
    return f"{hour12} {'AM' if ts.hour < 12 else 'PM'}"


def segment_evidence(detail: SegmentDetail) -> Evidence:
    ups = [f for f in detail.factors if f.points > 0][:MAX_FACTORS]
    downs = [f for f in detail.factors if f.points < 0][:1]
    # Walker crash counts do not describe riding, so ride evidence carries only the total.
    walker = (
        {"pedestrian_crashes": round(detail.history.ped_crashes)} if detail.mode == "walk" else {}
    )
    history = {"crashes": round(detail.history.crashes), **walker, "period": detail.history.period}
    payload = {
        "mode": detail.mode,
        "street": detail.name,
        "score": detail.score,
        "band": detail.band,
        "time": _time_label(detail.at),
        "conditions": detail.condition_used.cond,
        "confidence": detail.confidence,
        "raises_risk": [{"factor": f.label, "points": f.points} for f in ups],
        "lowers_risk": [{"factor": f.label, "points": abs(f.points)} for f in downs],
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
