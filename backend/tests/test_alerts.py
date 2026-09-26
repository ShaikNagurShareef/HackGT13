"""Walk alerts and avoided hotspots."""

from __future__ import annotations

import pytest
from app.domain.alerts import avoided_segments, walk_alerts
from app.domain.route_metrics import EdgeStep

NAMES = ["A St", "B Ave", "C Blvd", "D Way"]


def step(seg: int, length: float, score: float) -> EdgeStep:
    return EdgeStep(edge=0, seg_id=seg, length_m=length, score=score)


@pytest.mark.unit
def test_contiguous_hot_steps_on_one_street_form_one_alert() -> None:
    steps = (step(0, 50, 20), step(1, 40, 95), step(1, 30, 97), step(2, 200, 30))

    alerts = walk_alerts(steps, NAMES)

    assert len(alerts) == 1
    assert (alerts[0].start_m, alerts[0].end_m) == (50, 120)
    assert alerts[0].names == ("B Ave",)
    assert alerts[0].score == 97


@pytest.mark.unit
def test_nearby_hotspots_merge_into_one_alert() -> None:
    steps = (step(1, 30, 95), step(0, 40, 10), step(2, 30, 92), step(0, 300, 10), step(3, 20, 99))

    alerts = walk_alerts(steps, NAMES)

    assert [a.names for a in alerts] == [("B Ave", "C Blvd"), ("D Way",)]
    assert alerts[0].stretches == 2


@pytest.mark.unit
def test_paths_away_from_roads_never_alert() -> None:
    assert walk_alerts((step(-1, 100, 99),), NAMES) == []


@pytest.mark.unit
def test_avoided_segments_lists_high_risk_fastest_streets_not_used() -> None:
    fastest = (step(0, 10, 80), step(1, 10, 95), step(2, 10, 40), step(1, 10, 95))
    chosen = (step(0, 10, 80), step(3, 10, 30))

    assert avoided_segments(fastest, chosen, NAMES) == [1]


@pytest.mark.unit
def test_avoided_dedupes_by_street_keeping_riskiest_segment() -> None:
    names = ["Peachtree Pl", "Peachtree Pl", "Spring St", "Other"]
    fastest = (step(0, 10, 84), step(1, 10, 98), step(2, 10, 97))
    chosen = (step(3, 10, 20),)

    assert avoided_segments(fastest, chosen, names) == [1, 2]


@pytest.mark.unit
def test_contiguous_hot_stretches_on_different_streets_merge() -> None:
    steps = (step(1, 200, 95), step(2, 30, 92))

    alerts = walk_alerts(steps, NAMES)

    assert len(alerts) == 1
    assert alerts[0].names == ("B Ave", "C Blvd")


@pytest.mark.unit
def test_unnamed_streets_are_spoken_generically_and_not_listed() -> None:
    names = ["Unnamed street", "B Ave"]
    steps = (step(0, 40, 95),)

    assert walk_alerts(steps, names)[0].names == ("a side street",)
    assert avoided_segments((step(0, 10, 99), step(1, 10, 99)), (), names) == [1]
