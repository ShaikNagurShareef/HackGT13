"""CLI: raw layers -> cleaned, de-duplicated crashes snapped to road segments.

Outputs (data/interim):
  crashes_timed.parquet    all timed crashes citywide, deduplicated, no PII
  crashes_yearly.parquet   ARC 2020-2024 year-only crashes citywide
  crash_segments.parquet   core-area crash -> road segment weights (both streams)
  ingest_report.json       records in / dropped by reason / snapped (PRD DATA-01)
"""

from __future__ import annotations

import json
import logging

import geopandas as gpd
import numpy as np
import pandas as pd

from pathpulse_data.config import INTERIM_DIR, RAW_DIR
from pathpulse_data.ingest.clean import NORMALIZERS, drop_invalid_coords, normalize_source
from pathpulse_data.ingest.dedupe import dedupe_timed
from pathpulse_data.ingest.snap import RoadIndex, snap_points
from pathpulse_data.network.coverage import contains

log = logging.getLogger(__name__)
UTM = "EPSG:32616"
YEARLY_SOURCE = "arc_crashes_2020_2024"


def load_normalized() -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    frames, report = [], {}
    for key in NORMALIZERS:
        raw = pd.read_parquet(RAW_DIR / f"{key}.parquet")
        norm = normalize_source(key, raw)
        kept, drops = drop_invalid_coords(norm)
        report[key] = {"records_in": len(raw), **drops, "kept": len(kept)}
        frames.append(kept)
    return pd.concat(frames, ignore_index=True), report


def in_core(df: pd.DataFrame) -> pd.Series:
    """Inside street-level coverage (the buffered City of Atlanta boundary)."""
    return pd.Series(contains(df["lon"].to_numpy(), df["lat"].to_numpy()), index=df.index)


def to_utm_xy(lon: pd.Series, lat: pd.Series) -> np.ndarray:
    pts = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs="EPSG:4326").to_crs(UTM)
    return np.column_stack([pts.x.to_numpy(), pts.y.to_numpy()])


def build_road_index() -> RoadIndex:
    roads = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").to_crs(UTM)
    nodes = gpd.read_parquet(INTERIM_DIR / "road_nodes.parquet").to_crs(UTM)
    node_xy = pd.DataFrame({"node": nodes["osmid"], "x": nodes.geometry.x, "y": nodes.geometry.y})
    return RoadIndex.from_frames(roads[["seg_id", "u", "v", "geometry"]], node_xy)


def snap_stream(index: RoadIndex, crashes: pd.DataFrame, stream: str) -> pd.DataFrame:
    core = crashes.loc[in_core(crashes)].reset_index(drop=True)
    snapped = snap_points(index, to_utm_xy(core["lon"], core["lat"]))
    attrs = core[["crash_id", "is_ped", "is_bike", "year", "ts", "severity"]]
    return snapped.merge(attrs, left_on="point_idx", right_index=True).assign(stream=stream)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    crashes, report = load_normalized()
    timed_raw = crashes.loc[crashes["time_precision"] == "minute"]
    timed, dedupe_report = dedupe_timed(timed_raw)
    timed = timed.assign(crash_id=[f"t{i}" for i in range(len(timed))])
    # ARC rows have no collision id and identical rows are distinct crashes geocoded to the
    # same intersection (93% no-injury), so only exact OBJECTID repeats are removed.
    yearly = crashes.loc[crashes["source"] == YEARLY_SOURCE].drop_duplicates(subset=["source_id"])
    yearly = yearly.assign(crash_id=[f"y{i}" for i in range(len(yearly))])

    index = build_road_index()
    snaps = pd.concat(
        [snap_stream(index, timed, "timed"), snap_stream(index, yearly, "yearly")],
        ignore_index=True,
    )
    timed.to_parquet(INTERIM_DIR / "crashes_timed.parquet", index=False)
    yearly.to_parquet(INTERIM_DIR / "crashes_yearly.parquet", index=False)
    snaps.to_parquet(INTERIM_DIR / "crash_segments.parquet", index=False)

    summary = _summary(timed, yearly, snaps)
    full = {"sources": report, "dedupe": dedupe_report, **summary}
    (INTERIM_DIR / "ingest_report.json").write_text(json.dumps(full, indent=2, default=str))
    log.info("ingest summary: %s", json.dumps(summary, default=str))


def _by_year(df: pd.DataFrame) -> dict[int, int]:
    return {int(y): int(n) for y, n in df.groupby("year").size().items()}


def _bike_stats(
    timed: pd.DataFrame, yearly: pd.DataFrame, snaps: pd.DataFrame
) -> dict[str, object]:
    """Cyclist crash counts in coverage: per source (before dedupe merges) and snapped."""
    out: dict[str, object] = {}
    for stream, df in (("timed", timed), ("yearly", yearly)):
        core = df.loc[in_core(df) & df["is_bike"]]
        snapped = snaps.loc[(snaps["stream"] == stream) & snaps["is_bike"], "crash_id"].nunique()
        sources = core["sources"] if "sources" in core.columns else core["source"]
        per_source = sources.str.split(";").explode().value_counts()
        out[stream] = {
            "core_bike": len(core),
            "snapped_bike": int(snapped),
            "by_source": {str(k): int(v) for k, v in per_source.items()},
        }
    return out


def _summary(timed: pd.DataFrame, yearly: pd.DataFrame, snaps: pd.DataFrame) -> dict[str, object]:
    def core_stats(df: pd.DataFrame, stream: str) -> dict[str, int]:
        core = df.loc[in_core(df)]
        snapped_ids = snaps.loc[snaps["stream"] == stream, "crash_id"].unique()
        return {
            "core_total": len(core),
            "core_ped": int(core["is_ped"].sum()),
            "snapped": len(snapped_ids),
            "snapped_ped": int(core.loc[core["crash_id"].isin(snapped_ids), "is_ped"].sum()),
            "dropped_far_from_road": len(core) - len(snapped_ids),
        }

    return {
        "timed": core_stats(timed, "timed"),
        "yearly": core_stats(yearly, "yearly"),
        "timed_ped_by_year": _by_year(timed.loc[in_core(timed) & timed["is_ped"]]),
        "yearly_ped_by_year": _by_year(yearly.loc[in_core(yearly) & yearly["is_ped"]]),
        "timed_bike_by_year": _by_year(timed.loc[in_core(timed) & timed["is_bike"]]),
        "yearly_bike_by_year": _by_year(yearly.loc[in_core(yearly) & yearly["is_bike"]]),
        "bike": _bike_stats(timed, yearly, snaps),
        "data_through": str(timed["ts"].max().date()),
    }


if __name__ == "__main__":
    main()
