"""Route safety summaries only carry known day parts."""

from __future__ import annotations

import pytest
from app.api.schemas import RouteSafetyOut
from pydantic import ValidationError

BASE = {
    "lit_share": None,
    "busy_share": 0.5,
    "help_points_within_100m": 1,
    "crimes_persons_nearby": 0,
}


@pytest.mark.unit
@pytest.mark.parametrize("part", ["night", "morning", "afternoon", "evening"])
def test_known_day_parts_are_accepted(part: str) -> None:
    assert RouteSafetyOut(**BASE, day_part=part).day_part == part


@pytest.mark.unit
def test_unknown_day_part_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RouteSafetyOut(**BASE, day_part="dusk")
