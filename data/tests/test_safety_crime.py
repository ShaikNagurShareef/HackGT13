"""Crime aggregation and banding: persons-only filter, day parts, EB smoothing, terciles."""

from __future__ import annotations

from datetime import UTC, date, datetime

import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.safety.banding import CRIME_BANDS, eb_relative_rate, tercile_bands
from pathpulse_data.safety.crime import clean_crimes, hex_counts, in_window
from pathpulse_data.safety.dayparts import DAY_PART_KEYS

LAT, LON = 33.7756, -84.3963


def _ms(ts: datetime) -> int:
    return int(ts.timestamp() * 1000)


def _raw(rows: list[tuple[str, str, datetime, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "NIBRS_Offense": off,
                "LocationType": loc,
                "OccurredFromDate": _ms(ts),
                "lat": lat,
                "lon": lon,
            }
            for off, loc, ts, lat, lon in rows
        ]
    )


STREET = "HIGHWAY_ROAD_ALLEY_STREET_SIDEWALK"
NOON_UTC = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)  # 12:00 in Atlanta (EDT)


@pytest.mark.unit
def test_clean_keeps_only_crimes_against_persons_in_public_places() -> None:
    raw = _raw(
        [
            ("Aggravated Assault", STREET, NOON_UTC, LAT, LON),
            ("Robbery", "PARKING_DROP_LOT_GARAGE", NOON_UTC, LAT, LON),
            ("Simple Assault", "RESIDENCE_HOME", NOON_UTC, LAT, LON),  # private dwelling
            ("Theft From Motor Vehicle", STREET, NOON_UTC, LAT, LON),  # property
            ("Drug/Narcotic Violations", STREET, NOON_UTC, LAT, LON),  # society
            ("Murder & Nonnegligent Manslaughter", STREET, NOON_UTC, 0.0, 0.0),  # bad coords
        ]
    )

    out = clean_crimes(raw)

    assert sorted(out["category"]) == ["Aggravated assault", "Robbery"]
    assert set(out.columns) == {"category", "occurred", "day_part", "lat", "lon"}


@pytest.mark.unit
def test_clean_assigns_atlanta_local_day_part() -> None:
    late = datetime(2026, 6, 2, 3, 30, tzinfo=UTC)  # 23:30 Atlanta -> night
    raw = _raw([("Robbery", STREET, NOON_UTC, LAT, LON), ("Robbery", STREET, late, LAT, LON)])

    out = clean_crimes(raw)

    assert list(out["day_part"]) == ["afternoon", "night"]
    assert out["occurred"].iloc[1].hour == 23


@pytest.mark.unit
def test_in_window_selects_trailing_days() -> None:
    raw = _raw(
        [
            ("Robbery", STREET, datetime(2025, 1, 1, 16, tzinfo=UTC), LAT, LON),
            ("Robbery", STREET, datetime(2026, 6, 1, 16, tzinfo=UTC), LAT, LON),
        ]
    )
    crimes = clean_crimes(raw)

    recent = in_window(crimes, date(2026, 9, 26), days=365)

    assert len(recent) == 1


@pytest.mark.unit
def test_hex_counts_by_day_part_align_to_cells() -> None:
    cell = h3.latlng_to_cell(LAT, LON, 9)
    other = sorted(set(h3.grid_disk(cell, 1)) - {cell})[0]
    crimes = pd.DataFrame(
        {
            "category": ["Robbery"] * 3,
            "occurred": pd.Timestamp("2026-06-01T12:00"),
            "day_part": ["night", "night", "morning"],
            "lat": [LAT] * 3,
            "lon": [LON] * 3,
        }
    )

    counts = hex_counts(crimes, pd.Index([cell, other]))

    assert list(counts.columns) == list(DAY_PART_KEYS)
    assert counts.loc[cell, "night"] == 2
    assert counts.loc[cell, "morning"] == 1
    assert counts.loc[other].sum() == 0
    assert counts.dtypes.map(lambda d: d.kind == "i").all()


@pytest.mark.unit
def test_eb_shrinks_small_exposure_toward_citywide_rate() -> None:
    # Same raw rate (count / exposure = 2), but one area has 100x less exposure.
    counts = np.array([2.0, 200.0, 50.0, 50.0, 10.0, 90.0])
    exposure = np.array([1.0, 100.0, 50.0, 60.0, 20.0, 70.0])

    rel = eb_relative_rate(counts, exposure)

    assert rel[0] < rel[1]  # the thin-evidence area is pulled toward the city mean
    assert np.all(rel > 0)


@pytest.mark.unit
def test_eb_zero_crimes_everywhere_is_flat() -> None:
    rel = eb_relative_rate(np.zeros(4), np.array([1.0, 2.0, 3.0, 4.0]))

    assert np.allclose(rel, rel[0])


@pytest.mark.unit
def test_tercile_bands_split_the_city_into_thirds() -> None:
    values = np.arange(9, dtype=float)

    bands = tercile_bands(values)

    assert list(bands) == ["lower"] * 3 + ["typical"] * 3 + ["higher"] * 3
    assert CRIME_BANDS == ("lower", "typical", "higher")


@pytest.mark.unit
def test_tercile_bands_ties_never_inflate_the_higher_band() -> None:
    values = np.array([1.0] * 8 + [5.0])

    bands = tercile_bands(values)

    assert (bands == "higher").sum() <= 1
