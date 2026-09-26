"""Deterministic explanations: always available, always valid (GEN-03)."""

from __future__ import annotations

from typing import Any

from app.services.explain.evidence import Evidence


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _is_ride(ev: Evidence) -> bool:
    return bool(ev.payload.get("mode", "walk") != "walk")


def _history_tail(p: dict[str, Any], ride: bool) -> str:
    hist = p["history"]
    if p["confidence"] == "limited":
        return "Few crashes are recorded here, so this estimate leans on street characteristics."
    if ride and "bike_crashes" in hist:
        return (
            f"It recorded {hist['crashes']} crashes in {hist['period']}, "
            f"{hist['bike_crashes']} involving people on bikes."
        )
    if ride:
        return f"It recorded {hist['crashes']} crashes in {hist['period']}."
    return (
        f"It recorded {hist['crashes']} crashes in {hist['period']}, "
        f"{hist['pedestrian_crashes']} involving pedestrians."
    )


def segment_text(ev: Evidence) -> str:
    p = ev.payload
    ride = _is_ride(ev)
    ups = [f["factor"].lower() for f in p["raises_risk"]]
    when = f"at {p['time']} in {p['conditions']} conditions"
    who = " for traffic risk to people on bikes and scooters" if ride else ""
    lead = f"{p['street']} scores {p['score']} ({p['band']}){who} {when}."
    if ups:
        lead += f" The biggest contributors are {_join(ups)}."
    return f"{lead} {_history_tail(p, ride)}"


def route_text(ev: Evidence) -> str:
    p = ev.payload
    lead = "For this ride, the" if _is_ride(ev) else "The"
    if "pathpro" not in p:
        streets = p["fastest"]["riskiest_streets"]
        extra = f" Its highest-risk stretch is {streets[0]}." if streets else ""
        return f"{lead} fastest route is already the lower-risk option.{extra}"
    pp = p["pathpro"]
    avoids = f" by avoiding {_join(pp['avoids'])}" if pp["avoids"] else ""
    text = (
        f"{lead} PathPro route adds {pp['extra_minutes']} min and cuts traffic-risk exposure "
        f"{pp['less_exposure_percent']}%{avoids}."
    )
    if p.get("unavoidable"):
        text += f" Both routes use {_join(p['unavoidable'])}, so stay alert there."
    return text


def render(ev: Evidence) -> str:
    return segment_text(ev) if ev.kind == "segment" else route_text(ev)
