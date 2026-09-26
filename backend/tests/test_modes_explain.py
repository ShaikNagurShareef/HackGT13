"""Explanations know the travel mode: ride text says riding, walk text is unchanged."""

from __future__ import annotations

import pytest
from app.services.explain import template
from app.services.explain.evidence import _with_numbers
from app.services.explain.providers import SYSTEM_PROMPT
from app.services.explain.validator import validation_errors

RIDE_ROUTE = _with_numbers(
    "route",
    {
        "mode": "bike",
        "time": "10 PM",
        "conditions": "dry",
        "fastest": {"minutes": 9, "score": 88, "riskiest_streets": ["Ponce de Leon Avenue"]},
        "pathpro": {
            "minutes": 11,
            "score": 61,
            "extra_minutes": 1.8,
            "less_exposure_percent": 42,
            "avoids": ["Ponce de Leon Avenue"],
        },
    },
)
RIDE_SEGMENT = _with_numbers(
    "segment",
    {
        "mode": "scooter",
        "street": "Edgewood Avenue",
        "score": 71,
        "band": "Elevated",
        "time": "10 PM",
        "conditions": "dry",
        "confidence": "high",
        "raises_risk": [{"factor": "Vehicle crashes on this street", "points": 20}],
        "lowers_risk": [],
        "history": {"crashes": 40, "period": "2020-2024"},
    },
)


@pytest.mark.unit
def test_prompt_covers_riding_and_keeps_the_pathpro_name() -> None:
    assert "riding" in SYSTEM_PROMPT
    assert "traffic risk to people on bikes and scooters" in SYSTEM_PROMPT
    assert "the PathPro route" in SYSTEM_PROMPT


@pytest.mark.unit
def test_ride_templates_talk_about_riding_and_validate() -> None:
    route = template.render(RIDE_ROUTE)
    segment = template.render(RIDE_SEGMENT)

    assert "ride" in route.lower() and "PathPro route" in route
    assert "bikes and scooters" in segment and "pedestrian" not in segment.lower()
    assert validation_errors(route, RIDE_ROUTE) == []
    assert validation_errors(segment, RIDE_SEGMENT) == []


@pytest.mark.unit
def test_ride_fastest_is_lower_risk_template_mentions_the_ride() -> None:
    ev = _with_numbers(
        "route",
        {
            "mode": "ebike",
            "time": "8 AM",
            "conditions": "wet",
            "fastest": {"minutes": 7, "score": 30, "riskiest_streets": []},
            "fastest_is_lower_risk": True,
        },
    )

    text = template.render(ev)

    assert "ride" in text.lower()
    assert validation_errors(text, ev) == []
