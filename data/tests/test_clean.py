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


def _crash_level(**extra: list[object]) -> pd.DataFrame:
    base: dict[str, list[object]] = {
        "OBJECTID": [1, 2, 3],
        "KABCO_Severity": ["(O) No Injury"] * 3,
        "Roadway__From_Crash_Report_": ["10th St"] * 3,
        "Intersection_Name__from_Crash_R": [None] * 3,
        "Intersection_Name__from_Crash_Report_": [None] * 3,
        "Intersecting_Roadway": [None] * 3,
        "lat": [33.78] * 3,
        "lon": [-84.38] * 3,
    }
    return pd.DataFrame({**base, **extra})


@pytest.mark.unit
def test_every_source_carries_a_bike_flag_column() -> None:
    assert "is_bike" in CANONICAL_COLUMNS


@pytest.mark.unit
def test_arc_yearly_bike_flag_from_bicycle_related() -> None:
    raw = _crash_level(
        Crash_Year=[2022, 2023, 2024],
        F__of_Pedestrians_per_crash=[0, 1, 0],
        Bicycle_Related__T_F_=["true", "false", None],
    )

    out = normalize_source("arc_crashes_2020_2024", raw)

    assert out["is_bike"].tolist() == [True, False, False]
    assert out["is_ped"].tolist() == [False, True, False]


@pytest.mark.unit
def test_pedbike_layer_splits_bicycle_from_pedestrian_mode() -> None:
    raw = _crash_level(
        Mode=["Pedestrian", "Bicycle", None],
        Date_and_Time=[1665573240000] * 3,
    )

    out = normalize_source("coa_pedbike_2022", raw)

    assert out["is_bike"].tolist() == [False, True, False]
    assert out["is_ped"].tolist() == [True, False, False]


@pytest.mark.unit
def test_marta_bike_flag_from_crash_mode() -> None:
    raw = _crash_level(
        Crash_Mode=["Auto", "Bicycle", "Pedestrian"],
        Date=["2023-05-02"] * 3,
        Time=["2:50:00 PM"] * 3,
    )

    out = normalize_source("marta_all_2023", raw)

    assert out["is_bike"].tolist() == [False, True, False]


@pytest.mark.unit
def test_ka_bike_flag_from_bicycle_related_or_travel_mode_not_scooter() -> None:
    raw = pd.DataFrame(
        {
            "Date_W_Time": [1665573240000] * 3,
            "Pedestrian_Related": ["false"] * 3,
            "Bicycle_Related": ["true", "false", "false"],
            "TravelMode": ["Vehicle Only", "Bicyclist", "Scooter Rider"],
            "KABCO_Severity": ["(A) Suspected Serious Injury"] * 3,
            "Roadway": ["Peachtree St"] * 3,
            "Intersecting_Roadway": [None] * 3,
            "lat": [33.78] * 3,
            "lon": [-84.38] * 3,
        }
    )

    out = normalize_source("coa_ka_since_2013", raw)

    assert out["is_bike"].tolist() == [True, True, False]


@pytest.mark.unit
def test_gt_bike_flag_from_pedal_cycle_harmful_event() -> None:
    raw = _crash_level(
        Most_Harmful_Event__Crash_Level_=["Pedestrian", '["Motor Vehicle in Motion"]', None],
        First_Harmful_Event__Unit_Order_=[None, '["Pedal-Cycle","Motor Vehicle"]', None],
        Date=["2023-05-02"] * 3,
        Time=["14:50"] * 3,
        Light_Conditions__Crash_Level_=["Daylight"] * 3,
        Surface_Condition__Crash_Level_=["Dry"] * 3,
    )

    out = normalize_source("gt_pedcyc_2021_2025", raw)

    assert out["is_bike"].tolist() == [False, True, False]


@pytest.mark.unit
def test_midtown_bike_flag_and_bicyclist_age_never_kept() -> None:
    raw = pd.DataFrame(
        {
            "Date_and_Time": ["01/01/2019 08:17 PM", "03/02/2020 07:00 AM"],
            "Pedestrian_Related": ["false", "false"],
            "Bicycle_Related": ["true", "false"],
            "Bicyclist_Age": ["29", None],
            "KABCO_Severity": ["(O) No Injury"] * 2,
            "Roadway": ["14Th St"] * 2,
            "Intersecting_Roadway": [None] * 2,
            "lat": [33.786] * 2,
            "lon": [-84.382] * 2,
        }
    )

    out = normalize_source("coa_midtown_2019_2023", raw)

    assert out["is_bike"].tolist() == [True, False]
    assert list(out.columns) == list(CANONICAL_COLUMNS)


@pytest.mark.unit
def test_sources_without_a_bike_field_default_to_false() -> None:
    raw = _crash_level(Date_and_Time=["01/01/2019 08:17 PM"] * 3, SHSP_Emphasis_Areas=[None] * 3)

    out = normalize_source("cap_downtown_2017_2021", raw)

    assert not out["is_bike"].any()
