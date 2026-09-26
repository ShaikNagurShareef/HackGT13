"""Normalize heterogeneous crash layers into one canonical schema (PRD DATA-01, EC-31).

Personal fields present in some sources (names, ages, narratives) are never carried over.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np
import pandas as pd

from pathpulse_data.config import THRESHOLDS, TZ

CANONICAL_COLUMNS: tuple[str, ...] = (
    "source",
    "source_id",
    "collision_id",
    "ts",
    "year",
    "time_precision",
    "lat",
    "lon",
    "is_ped",
    "severity",
    "light_report",
    "surface_report",
    "road",
    "cross_road",
)
PII_COLUMNS: tuple[str, ...] = (
    "Name",
    "Age",
    "Details_411",
    "Pedestrian_Age",
    "Pedestrian_Age__Crash_Level_",
    "Driver_Age__Crash_Level_",
    "Bicyclist_Age",
    "Scooter_Rider_Age",
    "mapUrl",
)
LOCAL_FORMAT = "%m/%d/%Y %I:%M %p"
_SEVERITY = re.compile(r"^\(([KABCO])\)")


def parse_local_string(values: pd.Series, fmt: str = LOCAL_FORMAT) -> pd.Series:
    naive = pd.to_datetime(values, format=fmt, errors="coerce")
    return naive.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")


def parse_epoch_ms(values: pd.Series, wall_clock: bool = False) -> pd.Series:
    """ArcGIS dates are epoch ms in UTC, but some layers store local wall-clock time as UTC.

    `wall_clock=True` reads the UTC digits as Atlanta local time. Which mode a source needs
    was verified by agreement between reported light condition and solar light (ingest report).
    """
    naive = pd.to_datetime(pd.to_numeric(values, errors="coerce"), unit="ms")
    if wall_clock:
        return naive.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")
    return naive.dt.tz_localize("UTC").dt.tz_convert(TZ)


def parse_date_time(dates: pd.Series, times: pd.Series) -> pd.Series:
    joined = dates.astype("string").str.strip() + " " + times.astype("string").str.strip()
    naive = pd.to_datetime(joined, errors="coerce", format="mixed")
    return naive.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")


def severity_letter(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    match = _SEVERITY.match(raw)
    return match.group(1) if match else None


def _truthy(values: pd.Series) -> pd.Series:
    return values.astype("string").str.lower().isin({"true", "1", "yes"}).fillna(False)


def _col(raw: pd.DataFrame, name: str) -> pd.Series:
    return raw[name] if name in raw.columns else pd.Series([None] * len(raw), index=raw.index)


def _clean_id(values: pd.Series) -> list[str | None]:
    def one(v: object) -> str | None:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        text = str(v).strip()
        return text if text.isdigit() else None

    return [one(v) for v in values]


def _frame(
    raw: pd.DataFrame,
    source: str,
    ts: pd.Series,
    is_ped: pd.Series,
    cols: dict[str, str],
    year: pd.Series | None = None,
) -> pd.DataFrame:
    years = year if year is not None else ts.dt.year
    out = pd.DataFrame(
        {
            "source": source,
            "source_id": _col(raw, "OBJECTID").astype("string"),
            "collision_id": _clean_id(_col(raw, "Collision_ID")),
            "ts": ts,
            "year": pd.to_numeric(years, errors="coerce").astype("Int64"),
            "time_precision": "year" if year is not None else "minute",
            "lat": pd.to_numeric(raw["lat"], errors="coerce"),
            "lon": pd.to_numeric(raw["lon"], errors="coerce"),
            "is_ped": is_ped.astype(bool).to_numpy(),
            "severity": _col(raw, cols["severity"]).map(severity_letter),
            "light_report": _col(raw, cols.get("light", "")),
            "surface_report": _col(raw, cols.get("surface", "")),
            "road": _col(raw, cols["road"]),
            "cross_road": _col(raw, cols["cross"]),
        }
    )
    return out.loc[:, list(CANONICAL_COLUMNS)].reset_index(drop=True)


_CRASH_LEVEL = {
    "severity": "KABCO_Severity",
    "light": "Light_Conditions__Crash_Level_",
    "surface": "Surface_Condition__Crash_Level_",
    "road": "Roadway__From_Crash_Report_",
    "cross": "Intersection_Name__from_Crash_R",
}
_COA_DETAIL = {
    "severity": "KABCO_Severity",
    "light": "Light_Conditions",
    "surface": "Surface_Conditions",
    "road": "Roadway",
    "cross": "Intersecting_Roadway",
}


def _arc_yearly(raw: pd.DataFrame) -> pd.DataFrame:
    is_ped = pd.to_numeric(_col(raw, "F__of_Pedestrians_per_crash"), errors="coerce") > 0
    ts = pd.Series(pd.NaT, index=raw.index, dtype=f"datetime64[ns, {TZ.key}]")
    cols = {
        "severity": "KABCO_Severity",
        "road": "Roadway__From_Crash_Report_",
        "cross": "Intersecting_Roadway",
    }
    return _frame(raw, "arc_crashes_2020_2024", ts, is_ped, cols, year=raw["Crash_Year"])


def _coa_pedbike(raw: pd.DataFrame) -> pd.DataFrame:
    is_ped = _col(raw, "Mode").astype("string").str.contains("Ped", na=False)
    ts = parse_epoch_ms(raw["Date_and_Time"], wall_clock=True)
    return _frame(raw, "coa_pedbike_2022", ts, is_ped, _CRASH_LEVEL)


def _coa_all(raw: pd.DataFrame) -> pd.DataFrame:
    is_ped = pd.Series(False, index=raw.index)  # ped flag recovered by dedupe vs pedbike layer
    ts = parse_local_string(raw["Date_and_Time"])
    return _frame(raw, "coa_all_2022", ts, is_ped, _CRASH_LEVEL)


def _cap(raw: pd.DataFrame) -> pd.DataFrame:
    is_ped = _col(raw, "SHSP_Emphasis_Areas").astype("string").str.contains("edestrian", na=False)
    ts = parse_local_string(raw["Date_and_Time"])
    return _frame(raw, "cap_downtown_2017_2021", ts, is_ped, _CRASH_LEVEL)


def _midtown(raw: pd.DataFrame) -> pd.DataFrame:
    ts = parse_local_string(raw["Date_and_Time"])
    return _frame(raw, "coa_midtown_2019_2023", ts, _truthy(raw["Pedestrian_Related"]), _COA_DETAIL)


def _ka(raw: pd.DataFrame) -> pd.DataFrame:
    mode = _col(raw, "TravelMode").astype("string").str.contains("Ped", na=False)
    is_ped = _truthy(raw["Pedestrian_Related"]) | mode
    return _frame(raw, "coa_ka_since_2013", parse_epoch_ms(raw["Date_W_Time"]), is_ped, _COA_DETAIL)


def _gt(raw: pd.DataFrame) -> pd.DataFrame:
    most = _col(raw, "Most_Harmful_Event__Crash_Level_").astype("string")
    first = _col(raw, "First_Harmful_Event__Unit_Order_").astype("string")
    is_ped = most.str.contains("Pedestrian", na=False) | first.str.contains("Pedestrian", na=False)
    ts = parse_date_time(raw["Date"], raw["Time"])
    cols = {
        **_CRASH_LEVEL,
        "light": "Light_Conditions__Crash_Level_",
        "cross": "Intersection_Name__from_Crash_Report_",
    }
    return _frame(raw, "gt_pedcyc_2021_2025", ts, is_ped, cols)


def _marta(raw: pd.DataFrame) -> pd.DataFrame:
    peds = pd.to_numeric(_col(raw, "F__of_Pedestrians_per_crash"), errors="coerce").fillna(0)
    is_ped = _col(raw, "Crash_Mode").astype("string").eq("Pedestrian").fillna(False) | (peds > 0)
    ts = parse_date_time(raw["Date"], raw["Time"])
    cols = {**_CRASH_LEVEL, "cross": "Intersecting_Roadway"}
    return _frame(
        raw.drop(columns=list(PII_COLUMNS), errors="ignore"), "marta_all_2023", ts, is_ped, cols
    )


NORMALIZERS: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "arc_crashes_2020_2024": _arc_yearly,
    "coa_pedbike_2022": _coa_pedbike,
    "coa_all_2022": _coa_all,
    "cap_downtown_2017_2021": _cap,
    "coa_midtown_2019_2023": _midtown,
    "coa_ka_since_2013": _ka,
    "gt_pedcyc_2021_2025": _gt,
    "marta_all_2023": _marta,
}


def normalize_source(key: str, raw: pd.DataFrame) -> pd.DataFrame:
    return NORMALIZERS[key](raw)


def drop_invalid_coords(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Drop missing, (0,0), and out-of-Georgia coordinates; report counts per reason."""
    west, south, east, north = THRESHOLDS.georgia_bounds
    missing = df["lat"].isna() | df["lon"].isna()
    zero = ~missing & (df["lat"].abs() < 1e-6) & (df["lon"].abs() < 1e-6)
    inside = df["lon"].between(west, east) & df["lat"].between(south, north)
    outside = ~missing & ~zero & ~inside
    kept = df.loc[~(missing | zero | outside)].reset_index(drop=True)
    report = {
        "missing_coords": int(missing.sum()),
        "zero_coords": int(zero.sum()),
        "outside_georgia": int(outside.sum()),
    }
    return kept, report
