"""Deterministic explanations: always available, always valid (GEN-03)."""

from __future__ import annotations

from app.services.explain.evidence import Evidence


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def segment_text(ev: Evidence) -> str:
    p = ev.payload
    ups = [f["factor"].lower() for f in p["raises_risk"]]
    when = f"at {p['time']} in {p['conditions']} conditions"
    lead = f"{p['street']} scores {p['score']} ({p['band']}) {when}."
    if ups:
        lead += f" The biggest contributors are {_join(ups)}."
    hist = p["history"]
    if p["confidence"] == "limited":
        tail = "Few crashes are recorded here, so this estimate leans on street characteristics."
    else:
        tail = (
            f"It recorded {hist['crashes']} crashes in {hist['period']}, "
            f"{hist['pedestrian_crashes']} involving pedestrians."
        )
    return f"{lead} {tail}"


def route_text(ev: Evidence) -> str:
    p = ev.payload
    if "pathpulse" not in p:
        streets = p["fastest"]["riskiest_streets"]
        extra = f" Its highest-risk stretch is {streets[0]}." if streets else ""
        return f"The fastest route is already the lower-risk option.{extra}"
    pp = p["pathpulse"]
    avoids = f" by avoiding {_join(pp['avoids'])}" if pp["avoids"] else ""
    text = (
        f"The PathPulse route adds {pp['extra_minutes']} min and cuts traffic-risk exposure "
        f"{pp['less_exposure_percent']}%{avoids}."
    )
    if p.get("unavoidable"):
        text += f" Both routes use {_join(p['unavoidable'])}, so stay alert there."
    return text


def render(ev: Evidence) -> str:
    return segment_text(ev) if ev.kind == "segment" else route_text(ev)
