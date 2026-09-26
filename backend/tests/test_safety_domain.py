"""Safety domain: day parts, after-dark test, signal penalty, known-length shares, densify."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest
from app.domain.safety import (
    BUSY,
    DAY_PART_KEYS,
    LIT,
    MODERATE,
    QUIET,
    UNKNOWN,
    UNLIT,
    EdgeSignals,
    busier_share,
    day_part_for_hour,
    densify,
    is_after_dark,
    known_share,
    signal_penalty,
)
from app.domain.timeutil import ATLANTA


@pytest.mark.unit
@pytest.mark.parametrize(
    ("hour", "part"),
    [(22, "night"), (3, "night"), (5, "night"), (6, "morning"), (12, "afternoon"), (21, "evening")],
)
def test_day_part_for_hour(hour: int, part: str) -> None:
    assert day_part_for_hour(hour) == part


@pytest.mark.unit
def test_day_part_rejects_out_of_range_hour() -> None:
    with pytest.raises(ValueError, match="hour"):
        day_part_for_hour(24)


@pytest.mark.unit
def test_is_after_dark_uses_the_sun_not_the_clock() -> None:
    assert is_after_dark(datetime(2026, 9, 25, 22, 30, tzinfo=ATLANTA))
    assert not is_after_dark(datetime(2026, 9, 25, 12, 0, tzinfo=ATLANTA))
    assert is_after_dark(datetime(2026, 12, 21, 18, 30, tzinfo=ATLANTA))  # winter dusk
    assert not is_after_dark(datetime(2026, 6, 21, 20, 0, tzinfo=ATLANTA))  # summer evening


@pytest.mark.unit
def test_signal_penalty_only_penalizes_known_unlit_and_quiet() -> None:
    signals = EdgeSignals(
        lit=np.array([UNLIT, LIT, UNKNOWN, UNKNOWN], np.int8),
        activity=np.array([[QUIET] * 4, [BUSY] * 4, [UNKNOWN] * 4, [QUIET] * 4], np.int8),
    )

    penalty = signal_penalty(signals, "night")

    assert penalty[1] == 1.0 and penalty[2] == 1.0  # lit/busy and unknown are neutral
    assert penalty[0] > penalty[3] > 1.0
    assert DAY_PART_KEYS == ("night", "morning", "afternoon", "evening")


@pytest.mark.unit
def test_known_share_needs_half_the_length_known() -> None:
    lengths = np.array([100.0, 100.0, 100.0])

    assert known_share(lengths, np.array([LIT, UNLIT, UNKNOWN]), LIT) == pytest.approx(0.5)
    assert known_share(lengths, np.array([LIT, UNKNOWN, UNKNOWN]), LIT) is None
    assert known_share(np.zeros(0), np.zeros(0, np.int8), LIT) is None


@pytest.mark.unit
def test_densify_samples_long_edges() -> None:
    coords = [[-84.40, 33.77], [-84.40, 33.771]]  # ~111 m

    pts = densify(coords, step_m=20.0)

    assert len(pts) >= 6
    assert pts[0].tolist() == coords[0]
    assert pts[-1].tolist() == coords[-1]


@pytest.mark.unit
def test_densify_handles_single_point() -> None:
    assert len(densify([[-84.4, 33.77]], step_m=20.0)) == 1


@pytest.mark.unit
def test_busier_share_counts_moderate_and_busy_as_busier() -> None:
    lengths = np.array([100.0, 100.0, 100.0, 100.0])

    share = busier_share(lengths, np.array([QUIET, MODERATE, BUSY, UNKNOWN]))

    assert share == pytest.approx(2 / 3)
    assert busier_share(lengths, np.array([UNKNOWN, UNKNOWN, UNKNOWN, QUIET])) is None
