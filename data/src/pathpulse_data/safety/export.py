"""CLI: add the personal-safety layer to a bundle as new files (existing files untouched).

Usage:
  uv run --package pathpulse-data python -m pathpulse_data.safety.export [--link]

Copies artifacts/current to a new artifacts/<model_version>/, writes safety_meta.json,
safety_hexes.json, help_points.json, segment_safety.npy and edge_safety.npy, and records
their sha256 in the manifest. `--link` repoints artifacts/current at the new version.
Run `python -m pathpulse_data.safety.fetch` first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pathpulse_data.citywide.hexgrid import cells_for
from pathpulse_data.config import ARTIFACTS_DIR, INTERIM_DIR, RAW_DIR
from pathpulse_data.network.layers import UTM, load_streetlight
from pathpulse_data.safety import activity as act
from pathpulse_data.safety import helppoints as hp
from pathpulse_data.safety import lighting as lt
from pathpulse_data.safety.assemble import (
    EDGE_COLUMNS,
    SEGMENT_COLUMNS,
    HexSafety,
    crime_bands,
    edge_matrix,
    hexes_json,
    segment_matrix,
)
from pathpulse_data.safety.crime import clean_crimes, hex_counts, in_window
from pathpulse_data.safety.dayparts import DAY_PART_KEYS, DAY_PARTS, daypart_rates
from pathpulse_data.safety.sources import CRIME_CATEGORIES, EXCLUDED_LOCATIONS, SOURCES

log = logging.getLogger(__name__)
SAFETY_FILES = (
    "safety_meta.json",
    "safety_hexes.json",
    "help_points.json",
    "segment_safety.npy",
    "edge_safety.npy",
)
SHIPPED_DAYS, STABLE_DAYS = 365, 730
LAMP_RADIUS_M = 25.0
ALL_DAYS, WEEKDAY, WEEKEND = 0, 1, 2
WEEKDAY_SHARE = 5 / 7


def _dump(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))


def _load_hex_grid(bundle: Path) -> tuple[pd.Index, np.ndarray, np.ndarray]:
    meta = json.loads((bundle / "hex_meta.json").read_text())
    return pd.Index(meta["cells"]), np.asarray(meta["lat"]), np.asarray(meta["lon"])


def _crimes(cells: pd.Index) -> tuple[pd.DataFrame, pd.DataFrame, date, dict[str, int]]:
    raw = pd.read_parquet(RAW_DIR / "safety_apd_crime.parquet")
    crimes = clean_crimes(raw)
    through = crimes["occurred"].max().date()
    shipped = in_window(crimes, through, SHIPPED_DAYS)
    stable = in_window(crimes, through, STABLE_DAYS)
    stats = {
        "raw_rows": len(raw),
        "kept_24mo": len(stable),
        "kept_12mo": len(shipped),
        "in_city_12mo": int(pd.Series(cells_for(shipped["lat"], shipped["lon"])).isin(cells).sum()),
        **{f"12mo_{k}": int(v) for k, v in shipped["category"].value_counts().items()},
    }
    return hex_counts(shipped, cells), hex_counts(stable, cells), through, stats


def _streetlight_rates() -> pd.DataFrame:
    """Mean hourly pedestrian activity per StreetLight zone and day part (all days)."""
    sl = load_streetlight()
    sl = sl.loc[(sl["day_type"] == ALL_DAYS) & (sl["day_part"] > 0)]
    daily = sl.pivot_table(index="Zone_ID", columns="day_part", values="volume", aggfunc="mean")
    pos = sl.groupby("Zone_ID")[["lat", "lon"]].first()
    return daypart_rates(daily).join(pos)


def _segment_activity(n_seg: int, thresholds: tuple[float, float]) -> np.ndarray:
    vol = pd.read_parquet(INTERIM_DIR / "segment_ped_volume.parquet")
    wide = vol.pivot_table(index="seg_id", columns=["day_type", "day_part"], values="volume")
    parts = sorted(set(wide.columns.get_level_values("day_part")))
    blended = {}
    for p in parts:
        wd, we = wide.get((WEEKDAY, p)), wide.get((WEEKEND, p))
        pair = pd.concat([wd, we], axis=1, keys=["wd", "we"])
        weights = np.array([WEEKDAY_SHARE, 1 - WEEKDAY_SHARE])
        known = pair.notna().to_numpy()
        w = known * weights
        blended[p] = (pair.fillna(0).to_numpy() * w).sum(1) / np.where(
            w.sum(1) > 0, w.sum(1), np.nan
        )
    daily = pd.DataFrame(blended, index=wide.index).reindex(pd.RangeIndex(n_seg))
    rates = daypart_rates(daily)
    return np.column_stack([act.band_codes(rates[k].to_numpy(), thresholds) for k in DAY_PART_KEYS])


def _lamps_utm() -> list[shapely.Point]:
    osm = pd.read_parquet(RAW_DIR / "safety_osm.parquet")
    osm_lamps = osm.loc[osm["highway"] == "street_lamp", ["lon", "lat"]]
    downtown = pd.read_parquet(RAW_DIR / "coa_downtown_lights.parquet")[["lon", "lat"]]
    pts = pd.concat([osm_lamps, downtown]).dropna()
    geo = gpd.GeoSeries(gpd.points_from_xy(pts["lon"], pts["lat"]), crs="EPSG:4326").to_crs(UTM)
    return list(geo)


def _lighting(
    walk: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, edge_seg: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int]:
    lamps = _lamps_utm()
    road_tag = np.array([lt.parse_lit(v) for v in roads["lit"].astype(object)], np.int8)
    road_near = lt.lamps_near(list(roads.to_crs(UTM).geometry), lamps, LAMP_RADIUS_M)
    seg_lit = lt.edge_lit(road_tag, np.full(len(roads), lt.UNKNOWN, np.int8), road_near)
    own = np.array([lt.parse_lit(v) for v in walk["lit"].astype(object)], np.int8)
    via_seg = np.where(edge_seg >= 0, seg_lit[np.maximum(edge_seg, 0)], lt.UNKNOWN)
    near = lt.lamps_near(list(walk.to_crs(UTM).geometry), lamps, LAMP_RADIUS_M)
    return lt.edge_lit(own, via_seg.astype(np.int8), near), seg_lit, len(lamps)


def _midpoints(frame: gpd.GeoDataFrame) -> np.ndarray:
    mids = gpd.GeoSeries(
        shapely.line_interpolate_point(frame.to_crs(UTM).geometry.to_numpy(), 0.5, normalized=True),
        crs=UTM,
    ).to_crs("EPSG:4326")
    return np.column_stack([mids.x.to_numpy(), mids.y.to_numpy()])


def _help_points() -> pd.DataFrame:
    osm = hp.osm_help_points(pd.read_parquet(RAW_DIR / "safety_osm.parquet"))
    boxes = hp.callbox_points(pd.read_parquet(RAW_DIR / "safety_gt_callboxes.parquet"))
    return hp.dedupe_points(pd.concat([boxes, osm], ignore_index=True))


def build(bundle: Path) -> dict[str, Any]:
    """Compute every safety output for `bundle` (whose hex grid and walk graph are reused)."""
    cells, lat, lon = _load_hex_grid(bundle)
    counts_12, counts_24, through, crime_stats = _crimes(cells)
    zones = _streetlight_rates()
    hex_act = act.hex_activity(zones, cells)
    thresholds = act.activity_thresholds(hex_act)
    with np.load(bundle / "walk_graph.npz") as npz:
        edge_seg, edge_len = npz["edge_seg"], npz["edge_len"]
    walk = gpd.read_parquet(INTERIM_DIR / "walk_edges.parquet")
    roads = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").sort_values("seg_id")
    if len(walk) != len(edge_seg):
        raise RuntimeError("walk_edges.parquet does not match the bundle's walk graph")
    edge_lit, seg_lit, n_lamps = _lighting(walk, roads, edge_seg)
    mids = _midpoints(walk)
    edge_cells = cells_for(mids[:, 1], mids[:, 0])
    lit_share = lt.hex_lit_share(
        pd.DataFrame({"cell": edge_cells, "length": edge_len, "lit": edge_lit}), cells
    )
    helps = _help_points()
    seg_act = _segment_activity(len(roads), thresholds)
    seg_help = hp.nearest_distance_m(_midpoints(roads), helps[["lon", "lat"]].to_numpy(float))
    table = HexSafety(
        cells=cells,
        lat=lat,
        lon=lon,
        crimes_12mo=counts_12,
        crime_band=crime_bands(counts_24, hex_act),
        lit_share=lit_share,
        activity=pd.DataFrame(
            {k: act.band_codes(hex_act[k].to_numpy(), thresholds) for k in DAY_PART_KEYS},
            index=cells,
        ),
        help_points=hp.hex_help_counts(helps, cells),
    )
    in_city = pd.Series(edge_cells).isin(cells).to_numpy()
    stats = {
        "crime": crime_stats,
        "hexes": len(cells),
        "hexes_with_lit_share": int(lit_share.notna().sum()),
        "walk_length_known_lit_share": round(
            float(edge_len[in_city & (edge_lit != lt.UNKNOWN)].sum() / edge_len[in_city].sum()), 4
        ),
        "walk_length_lit_share": round(
            float(edge_len[in_city & (edge_lit == lt.LIT)].sum() / edge_len[in_city].sum()), 4
        ),
        "lamps": n_lamps,
        "hexes_with_activity": int(hex_act.notna().any(axis=1).sum()),
        "segments_with_activity": int((seg_act[:, 0] >= 0).sum()),
        "activity_thresholds_per_hour": [round(t, 2) for t in thresholds],
        "help_points": {k: int(v) for k, v in helps["kind"].value_counts().items()},
    }
    return {
        "hexes": hexes_json(table),
        "help_points": helps.round({"lat": 6, "lon": 6}).to_dict(orient="records"),
        "segment_safety": segment_matrix(seg_lit, seg_act, seg_help),
        "edge_safety": edge_matrix(edge_lit, edge_seg, seg_act),
        "data_through": through.isoformat(),
        "stats": stats,
    }


def _meta(result: dict[str, Any]) -> dict[str, Any]:
    through = date.fromisoformat(result["data_through"])
    return {
        "data_through": result["data_through"],
        "window_days": SHIPPED_DAYS,
        "band_window_days": STABLE_DAYS,
        "window_start": (through - pd.Timedelta(days=SHIPPED_DAYS - 1)).isoformat(),
        "sources": [{"name": s.name, "url": s.url, "license": s.license} for s in SOURCES],
        "crime_categories": sorted(set(CRIME_CATEGORIES.values())),
        "excluded_locations": sorted(EXCLUDED_LOCATIONS),
        "day_parts": [{"key": p.key, "label": p.label, "hours": list(p.hours)} for p in DAY_PARTS],
        "segment_columns": list(SEGMENT_COLUMNS),
        "edge_columns": list(EDGE_COLUMNS),
        "method": (
            "Crimes per hex and day part over 24 months, Empirical-Bayes (Poisson-Gamma) "
            "smoothed per unit of StreetLight pedestrian activity. 'higher'/'lower' when the "
            "posterior probability of being above/below the citywide rate is >= 0.9; a hex "
            "with no reports is never 'higher'."
        ),
        "stats": result["stats"],
    }


def write_safety(out: Path, result: dict[str, Any]) -> None:
    """Write the safety files into `out` and add their sha256 to its manifest."""
    _dump(out / "safety_meta.json", _meta(result))
    _dump(out / "safety_hexes.json", result["hexes"])
    _dump(out / "help_points.json", result["help_points"])
    np.save(out / "segment_safety.npy", result["segment_safety"])
    np.save(out / "edge_safety.npy", result["edge_safety"])
    manifest = json.loads((out / "manifest.json").read_text())
    for name in SAFETY_FILES:
        manifest["files"][name] = hashlib.sha256((out / name).read_bytes()).hexdigest()
    manifest["safety"] = {"data_through": result["data_through"], "files": list(SAFETY_FILES)}
    _dump(out / "manifest.json", manifest)


def add_safety(out: Path) -> None:
    """Pipeline hook (export/bundle.py): skip with a warning when raw pulls are missing."""
    if not (RAW_DIR / "safety_apd_crime.parquet").exists():
        log.warning("safety raw data missing; run pathpulse_data.safety.fetch (bundle unchanged)")
        return
    write_safety(out, build(out))


def new_version(source: Path) -> Path:
    from pathpulse_data.export.bundle import model_version

    version = model_version()
    out = ARTIFACTS_DIR / version
    shutil.copytree(source, out)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["model_version"] = version
    manifest["derived_from"] = source.name
    manifest["safety_added_at"] = datetime.now(UTC).isoformat()
    _dump(out / "manifest.json", manifest)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--link", action="store_true", help="point artifacts/current here")
    args = parser.parse_args()
    source = (ARTIFACTS_DIR / "current").resolve()
    result = build(source)
    out = new_version(source)
    write_safety(out, result)
    if args.link:
        current = ARTIFACTS_DIR / "current"
        current.unlink()
        current.symlink_to(out.name)
    log.info("safety bundle %s | %s", out.name, json.dumps(result["stats"]))


if __name__ == "__main__":
    main()
