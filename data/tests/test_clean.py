"""Per-source crash normalizers -> one canonical schema, plus coordinate hygiene."""

from __future__ import annotations

import pandas as pd
import pytest
from pathpulse_data.ingest.clean import (
    CANONICAL_COLUMNS,
    PII_COLUMNS,
    drop_invalid_coords,
    normalize_source,
    parse_epoch_ms,
    parse_local_string,
    severity_letter,
)


@pytest.mark.unit
def test_parse_local_string_is_new_york_aware() -> None:
    ts = parse_local_string(pd.Series(["01/01/2019 08:17 PM", "bad"]))

    assert ts.iloc[0].hour == 20
    assert str(ts.iloc[0].tz) == "America/New_York"
    assert pd.isna(ts.iloc[1])


@pytest.mark.unit
def test_parse_epoch_ms_utc_vs_wall_clock() -> None:
    ms = pd.Series([1665573240000])  # 2022-10-12 11:14 in UTC digits

    utc = parse_epoch_ms(ms)
    wall = parse_epoch_ms(ms, wall_clock=True)

    assert utc.iloc[0].hour == 7  # EDT = UTC-4
    assert wall.iloc[0].hour == 11
    assert str(wall.iloc[0].tz) == "America/New_York"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "letter"),
    [
        ("(K) Fatal Injury", "K"),
        ("(A) Suspected Serious Injury", "A"),
        ("(O) No Injury", "O"),
        (None, None),
        ("garbage", None),
    ],
)
def test_severity_letter(raw: str | None, letter: str | None) -> None:
    assert severity_letter(raw) == letter


@pytest.mark.unit
def test_normalize_midtown_flags_pedestrian_and_keeps_collision_id() -> None:
    raw = pd.DataFrame(
        {
            "Collision_ID": [7026172, 7026173],
            "Date_and_Time": ["01/01/2019 08:17 PM", "03/02/2020 07:00 AM"],
            "Pedestrian_Related": ["false", "true"],
            "KABCO_Severity": ["(O) No Injury", "(B) Suspected Minor/Visible Injury"],
            "Light_Conditions": ["Dark-Lighted", "Daylight"],
            "Surface_Conditions": ["Dry", "Wet"],
            "Roadway": ["14Th St", "Peachtree St"],
            "Intersecting_Roadway": ["Juniper St", None],
            "lat": [33.786, 33.780],
            "lon": [-84.382, -84.384],
        }
    )

    out = normalize_source("coa_midtown_2019_2023", raw)

    assert list(out.columns) == list(CANONICAL_COLUMNS)
    assert out["is_ped"].tolist() == [False, True]
    assert out["collision_id"].tolist() == ["7026172", "7026173"]
    assert out["time_precision"].unique().tolist() == ["minute"]
    assert out["surface_report"].tolist() == ["Dry", "Wet"]


@pytest.mark.unit
def test_normalize_marta_drops_pii_and_uses_date_time_fields() -> None:
    raw = pd.DataFrame(
        {
            "Name": ["SOMEONE"],
            "Age": ["66"],
            "Details_411": ["text"],
            "Collision_ID": ["Manually added"],
            "Date": ["2022-05-02"],
            "Time": ["2:50:00 AM"],
            "Crash_Mode": ["Pedestrian"],
            "F__of_Pedestrians_per_crash": [None],
            "KABCO_Severity": ["(K) Fatal Injury"],
            "Light_Conditions__Crash_Level_": [None],
            "Surface_Condition__Crash_Level_": [None],
            "Roadway__From_Crash_Report_": ["MORELAND AVENUE"],
            "Intersecting_Roadway": [None],
            "lat": [33.742],
            "lon": [-84.349],
        }
    )

    out = normalize_source("marta_all_2023", raw)

    assert not set(PII_COLUMNS) & set(out.columns)
    assert out["is_ped"].iloc[0]
    assert out["collision_id"].iloc[0] is None
    assert out["ts"].iloc[0].hour == 2


@pytest.mark.unit
def test_normalize_arc_year_only() -> None:
    raw = pd.DataFrame(
        {
            "OBJECTID": [1, 2],
            "Crash_Year": [2021, 2024],
            "F__of_Pedestrians_per_crash": [1, 0],
            "KABCO_Severity": ["(A) Suspected Serious Injury", "(O) No Injury"],
            "Roadway__From_Crash_Report_": ["North Ave", "Spring St"],
            "Intersecting_Roadway": ["Techwood Dr", None],
            "lat": [33.771, 33.772],
            "lon": [-84.391, -84.389],
        }
    )

    out = normalize_source("arc_crashes_2020_2024", raw)

    assert out["time_precision"].unique().tolist() == ["year"]
    assert out["ts"].isna().all()
    assert out["year"].tolist() == [2021, 2024]
    assert out["is_ped"].tolist() == [True, False]


@pytest.mark.unit
def test_unknown_source_raises() -> None:
    with pytest.raises(KeyError):
        normalize_source("nope", pd.DataFrame())


@pytest.mark.unit
def test_drop_invalid_coords_counts_reasons() -> None:
    df = pd.DataFrame({"lat": [33.77, 0.0, None, 40.7], "lon": [-84.39, 0.0, -84.0, -74.0]})

    kept, report = drop_invalid_coords(df)

    assert len(kept) == 1
    assert report == {"missing_coords": 1, "zero_coords": 1, "outside_georgia": 1}
