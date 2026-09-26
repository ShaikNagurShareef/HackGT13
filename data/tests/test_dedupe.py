"""Cross-source crash de-duplication (PRD EC-33)."""

from __future__ import annotations

import pandas as pd
import pytest
from pathpulse_data.config import TZ
from pathpulse_data.ingest.dedupe import dedupe_timed

BASE = pd.Timestamp("2022-10-12 19:14", tz=TZ)


def _row(
    source: str,
    minutes: float,
    dlat: float,
    *,
    ped: bool,
    sev: str,
    cid: str | None = None,
    bike: bool = False,
) -> dict[str, object]:
    return {
        "source": source,
        "source_id": "1",
        "collision_id": cid,
        "ts": BASE + pd.Timedelta(minutes=minutes),
        "year": 2022,
        "time_precision": "minute",
        "lat": 33.7700 + dlat,
        "lon": -84.3900,
        "is_ped": ped,
        "is_bike": bike,
        "severity": sev,
        "light_report": "Dark-Lighted",
        "surface_report": "Dry",
        "road": "North Ave",
        "cross_road": None,
    }


@pytest.mark.unit
def test_same_crash_in_two_sources_merges_and_keeps_ped_flag() -> None:
    df = pd.DataFrame(
        [
            _row("coa_all_2022", 0, 0.0, ped=False, sev="O"),
            _row("coa_pedbike_2022", 10, 0.0001, ped=True, sev="B"),  # ~11 m, 10 min later
        ]
    )

    out, report = dedupe_timed(df)

    assert len(out) == 1
    assert bool(out["is_ped"].iloc[0]) is True
    assert out["severity"].iloc[0] == "B"
    assert out["n_sources"].iloc[0] == 2
    assert report["merged"] == 1


@pytest.mark.unit
def test_far_apart_or_later_crashes_stay_separate() -> None:
    df = pd.DataFrame(
        [
            _row("a", 0, 0.0, ped=False, sev="O"),
            _row("b", 90, 0.0, ped=False, sev="O"),  # 90 minutes later
            _row("c", 0, 0.001, ped=False, sev="O"),  # ~111 m away
        ]
    )

    out, _ = dedupe_timed(df)

    assert len(out) == 3


@pytest.mark.unit
def test_shared_collision_id_merges_even_if_geocoded_differently() -> None:
    df = pd.DataFrame(
        [
            _row("midtown", 0, 0.0, ped=True, sev="A", cid="7026172"),
            _row("ka", 0, 0.002, ped=True, sev="A", cid="7026172"),
        ]
    )

    out, _ = dedupe_timed(df)

    assert len(out) == 1


@pytest.mark.unit
def test_severity_keeps_most_severe() -> None:
    df = pd.DataFrame(
        [
            _row("a", 0, 0.0, ped=True, sev="C"),
            _row("b", 1, 0.0, ped=True, sev="K"),
            _row("c", 2, 0.0, ped=True, sev=None),  # type: ignore[arg-type]
        ]
    )

    out, _ = dedupe_timed(df)

    assert out["severity"].iloc[0] == "K"


@pytest.mark.unit
def test_bike_flag_survives_merge_with_an_unflagged_all_mode_record() -> None:
    df = pd.DataFrame(
        [
            _row("coa_all_2022", 0, 0.0, ped=False, sev="O"),
            _row("coa_pedbike_2022", 5, 0.00005, ped=False, sev="C", bike=True),
            _row("coa_all_2022", 0, 0.01, ped=False, sev="O"),  # ~1.1 km away: separate
        ]
    )

    out, _ = dedupe_timed(df)

    assert sorted(out["is_bike"].tolist()) == [False, True]
    assert not out["is_ped"].any()
