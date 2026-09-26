"""CLI: ride (bike / e-bike / scooter) model -- features, honest evaluation, and export.

Usage (after `python -m pathpulse_data.network.bike` and `python -m pathpulse_data.ingest.run`):
  uv run --package pathpulse-data python -m pathpulse_data.ride.run features
  uv run --package pathpulse-data python -m pathpulse_data.ride.run export
  uv run --package pathpulse-data python -m pathpulse_data.ride.run link <version>

`export` copies artifacts/current to a new version, writes only `ride_*` files, verifies every
walk byte is unchanged, and records sha256 + manifest["modes"]. `link` repoints current.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from pathpulse_data.config import ARTIFACTS_DIR, INTERIM_DIR, RAW_DIR
from pathpulse_data.export import writers
from pathpulse_data.export.assemble import Assembled, assemble
from pathpulse_data.export.bundle import (
    SPATIAL_FINAL,
    SPATIAL_TEST,
    SPATIAL_VAL,
    TEMPORAL_FINAL,
    TEMPORAL_TEST,
    TEMPORAL_TRAIN,
    model_version,
)
from pathpulse_data.model.benchmark import benchmark
from pathpulse_data.model.dataset import SegmentData, load_segment_data, window_counts
from pathpulse_data.model.spatial import SpatialFit, density, fit_spatial
from pathpulse_data.model.temporal import CELL_KEYS, TemporalModel
from pathpulse_data.model.temporal_data import (
    cell_table,
    crash_cells,
    evaluate_temporal,
    fit_final,
    load_hours,
)
from pathpulse_data.network.bike import city_infra
from pathpulse_data.network.layers import UTM, load_lines
from pathpulse_data.ride import evaluate as rev
from pathpulse_data.ride.bundle import (
    RIDE_PREFIX,
    new_ride_version,
    register_ride,
    ride_name,
    verify_unchanged,
)
from pathpulse_data.ride.features import (
    BELTLINE_RADIUS_M,
    facility_by_segment,
    hex_trips,
    near_lines,
    ride_extra,
    strava_trips,
)
from pathpulse_data.ride.spec import RIDE_SPEC

log = logging.getLogger(__name__)
TARGET = "is_bike"
FEATURES_FILE = "ride_features.parquet"
EXPOSURE = "proxy"
EXPOSURE_DETAIL = (
    "No StreetLight bicycle layer is published by the City. Cyclist exposure is proxied by "
    "Strava Metro 2024 ride + e-bike trip origins/destinations per H3 res-8 hex (ARC), bike "
    "facility presence, and StreetLight 2021 pedestrian activity."
)
SOURCES = {
    "cyclist_crash_labels": "ARC Crashes 2020-2024 'Bicycle_Related (T/F)' (spatial model)",
    "cyclist_crash_timed": "COA 2022 ped/bike (Mode=Bicycle), MARTA-county 2023 (Crash_Mode), "
    "COA K/A since 2013 (Bicycle_Related / TravelMode=Bicyclist), Midtown 2019-23 "
    "(Bicycle_Related), GT 2021-25 (Pedal-Cycle harmful event); CAP and COA-all via dedupe",
    "bike_network": "OpenStreetMap via OSMnx network_type='bike' (ODbL)",
    "bike_facilities": "City of Atlanta Bike_Facilities_Public_View (Status=Existing), "
    "services2.arcgis.com/zLeajbicrDRLQcny/.../Bike_Facilities_Public_View/FeatureServer/0 "
    "(public City open data, no license text published)",
    "beltline": "OSM names (BeltLine / Eastside / Westside / Southside Trail) + ABI "
    "Atlanta_BeltLine layer (Status != Planning)",
    "cyclist_activity_proxy": "ARC Strava_Bike_Hexagons_WFL1 layers 9 (origins) and 4 "
    "(destinations), 2024 Ride+EBikeRide trip counts (Strava Metro via ARC; aggregated)",
}


# ----------------------------------------------------------------------------- features
def build_features() -> pd.DataFrame:
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").sort_values("seg_id")
    segs = segs.to_crs(UTM).reset_index(drop=True)
    edges = gpd.read_parquet(INTERIM_DIR / "bike_edges.parquet").to_crs(UTM)
    osm = edges[["geometry"]].assign(infra=edges["bike_infra"].astype(int))
    city = load_lines("coa_bike_facilities")
    city = city.assign(
        infra=[
            int(city_infra(t, s))
            for t, s in zip(city["SimpFacilityType"], city["Status"], strict=True)
        ]
    )
    infra_osm = facility_by_segment(segs, [osm])
    infra_city = facility_by_segment(segs, [city])
    abi = load_lines("coa_beltline")
    belt = pd.concat(
        [
            edges.loc[edges["beltline"], ["geometry"]],
            abi.loc[abi["Status"].astype(str) != "Planning", ["geometry"]],
        ],
        ignore_index=True,
    )
    mids = segs.geometry.interpolate(0.5, normalized=True).to_crs("EPSG:4326")
    trips = strava_trips(
        pd.read_parquet(RAW_DIR / "arc_strava_bike_origins.parquet"),
        pd.read_parquet(RAW_DIR / "arc_strava_bike_destinations.parquet"),
    )
    return pd.DataFrame(
        {
            "seg_id": segs["seg_id"].to_numpy(),
            "bike_infra": np.maximum(infra_osm.to_numpy(), infra_city.to_numpy()),
            "bike_infra_osm": infra_osm.to_numpy(),
            "bike_infra_city": infra_city.to_numpy(),
            "beltline_adjacent": near_lines(
                segs, gpd.GeoDataFrame(belt, crs=UTM), BELTLINE_RADIUS_M
            ).to_numpy(),
            "bike_trips": hex_trips(mids.y.to_numpy(), mids.x.to_numpy(), trips),
        }
    )


def features_main() -> None:
    feats = build_features()
    feats.to_parquet(INTERIM_DIR / FEATURES_FILE, index=False)
    log.info(
        "ride features: %d segments | infra %s | beltline %d | strava>0 %.3f",
        len(feats),
        feats["bike_infra"].value_counts().sort_index().to_dict(),
        int(feats["beltline_adjacent"].sum()),
        float((feats["bike_trips"] > 0).mean()),
    )


# ----------------------------------------------------------------------------- model
def load_ride_data(base: SegmentData) -> tuple[SegmentData, pd.DataFrame]:
    feats = pd.read_parquet(INTERIM_DIR / FEATURES_FILE).set_index("seg_id")
    feats = feats.reindex(base.features.index)
    return replace(base, target_col=TARGET, extra=ride_extra(feats)), feats


def _with_walk_reuse(
    bench: dict[str, Any],
    ride_fit: SpatialFit,
    ride: SegmentData,
    walk: SegmentData,
    test_year: int,
) -> dict[str, Any]:
    """Add 'Walk (pedestrian) model reused' + our gain CI over it to a ride benchmark."""
    walk_fit = fit_spatial(walk, ride_fit.train_years)
    observed = window_counts(ride, range(test_year, test_year + 1), ped=True).to_numpy()
    lengths = ride.features["length_m"].to_numpy(float)
    ours = density(ride_fit.expected(ride)["eb"], ride)
    other = density(walk_fit.expected(walk)["eb"], walk)
    blocks = ride.blocks.reindex(ride.features.index)
    row = rev.compare_method(rev.WALK_REUSE, ours, other, observed, lengths, blocks)
    return {**bench, "walk_model_reuse": row}


def evaluate_spatial(ride: SegmentData, walk: SegmentData) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, (train, test_year) in (
        ("spatial_test", SPATIAL_TEST),
        ("spatial_validation", SPATIAL_VAL),
    ):
        ride_fit = fit_spatial(ride, train)
        bench = benchmark(ride_fit, ride, test_year)
        out[key] = _with_walk_reuse(bench, ride_fit, ride, walk, test_year)
        log.info("ride %s done: %s", key, json.dumps(rev.targets(bench)))
    return out


def evaluate_time(hours: pd.DataFrame) -> tuple[dict[str, Any], str]:
    bike_cells = crash_cells(hours, TARGET)
    walk_cells = crash_cells(hours)
    own = evaluate_temporal(bike_cells, hours, TEMPORAL_TRAIN, TEMPORAL_TEST)
    walk_model = fit_final(walk_cells, hours, TEMPORAL_TRAIN)
    deviances = {
        "cyclist-specific": own["deviance_model"],
        "walk structure reused": rev.reuse_deviance(walk_model, bike_cells, hours, TEMPORAL_TEST),
        "all-mode shape": rev.reuse_deviance(
            walk_model, bike_cells, hours, TEMPORAL_TEST, target_task=False
        ),
    }
    choice = rev.choose_temporal(deviances)
    train_n = cell_table(bike_cells, hours, TEMPORAL_TRAIN).query("is_ped")["count"].sum()
    result = {
        **own,
        "train_bike_crashes": float(train_n),
        "deviance_by_choice": deviances,
        "choice": choice,
        "deviance_reduction_vs_flat": 1.0 - deviances[choice] / own["deviance_flat"],
    }
    return result, choice


def final_temporal(hours: pd.DataFrame, choice: str) -> tuple[TemporalModel, pd.DataFrame]:
    """Temporal model shipped with the ride frames, per the held-out choice."""
    cells = crash_cells(hours, TARGET if choice == "cyclist-specific" else "is_ped")
    model = fit_final(cells, hours, TEMPORAL_FINAL)
    if choice == "all-mode shape":
        model = replace(model, coef=model.coef.where(~model.coef.index.str.startswith("ped:"), 0.0))
    ref = cell_table(cells, hours, TEMPORAL_FINAL).query("is_ped")[[*CELL_KEYS, "hours"]]
    return model, ref


def headline(metrics: dict[str, Any]) -> dict[str, Any]:
    test = metrics["spatial_test"]
    methods = {m["method"]: m for m in test["methods"]}
    ours = methods[rev.OURS]
    val = {m["method"]: m for m in metrics["spatial_validation"]["methods"]}
    reuse = test["walk_model_reuse"]
    return {
        "capture_top10": ours["capture_top10"],
        "capture_top10_ci95": test["capture_top10_ci95"],
        "vs_random": ours["capture_top10"] / 0.10,
        "random_capture_top10": methods[rev.RANDOM]["capture_top10"],
        "count_only_capture_top10": methods[rev.COUNT_ONLY]["capture_top10"],
        "gain_vs_count_only_ci95": test["capture_gain_vs_count_only_ci95"],
        "hin_capture_top10": methods["City High Injury Network"]["capture_top10"],
        "model_only_capture_top10": methods["Model only (SPF)"]["capture_top10"],
        "walk_model_capture_top10": reuse["capture_top10"],
        "gain_vs_walk_model_ci95": reuse["gain_ci95"],
        "roc_auc": ours["roc_auc"],
        "observed_bike_crashes": test["observed_ped_crashes"],
        "validation_capture_top10": val[rev.OURS]["capture_top10"],
        "validation_count_only_capture_top10": val[rev.COUNT_ONLY]["capture_top10"],
        "temporal_model": metrics["temporal_test"]["choice"],
        "temporal_deviance_reduction_vs_flat": metrics["temporal_test"][
            "deviance_reduction_vs_flat"
        ],
        "targets": rev.targets(test),
        "test_year": test["test_year"],
    }


# ----------------------------------------------------------------------------- export
def _write_ride_files(
    out: Path, asm: Assembled, ride: SegmentData, feats: pd.DataFrame, metrics: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    bike_hist = window_counts(ride, SPATIAL_FINAL, ped=True).round(1)
    infra = feats["bike_infra"].fillna(0).astype(np.int64)
    writers.write_segments(
        out,
        asm,
        prefix=RIDE_PREFIX,
        extra_meta=pd.DataFrame(
            {"bike_crashes": bike_hist.to_numpy(), "bike_infra": infra.to_numpy()}
        ),
        extra_props={"b": infra.to_numpy()},
    )
    writers.write_factors(out, asm, spec=RIDE_SPEC, prefix=RIDE_PREFIX)
    writers.write_frames(out, asm, prefix=RIDE_PREFIX)
    graph = writers.write_graph(out, "bike", ride_name("walk_graph.npz"))
    n_hot = writers.write_hotspot_nodes(out, prefix=RIDE_PREFIX)
    writers._dump(out / ride_name("metrics.json"), metrics)
    files = sorted(p.name for p in out.iterdir() if p.name.startswith(RIDE_PREFIX))
    return files, {"ride_graph": graph, "ride_hotspot_nodes": n_hot}


def export_main() -> None:
    source = (ARTIFACTS_DIR / "current").resolve()
    src_manifest = json.loads((source / "manifest.json").read_text())
    base = load_segment_data()
    ride, feats = load_ride_data(base)
    hours = load_hours()
    temporal, choice = evaluate_time(hours)
    metrics: dict[str, Any] = {**evaluate_spatial(ride, base), "temporal_test": temporal}
    fit = fit_spatial(ride, SPATIAL_FINAL)
    tmodel, t_ref = final_temporal(hours, choice)
    today = date.fromisoformat(min(src_manifest["reference_dates"].values()))
    asm = assemble(fit, tmodel, t_ref, ride, today, spec=RIDE_SPEC)
    ingest = json.loads((INTERIM_DIR / "ingest_report.json").read_text())
    metrics |= {
        "headline": headline(metrics),
        "temporal_effects": asm.temporal_effects,
        "ingest_bike": {k: v for k, v in ingest.items() if "bike" in k},
        "exposure": EXPOSURE,
        "exposure_detail": EXPOSURE_DETAIL,
        "sources": SOURCES,
        "bike_infra_segments": {
            str(k): int(v) for k, v in feats["bike_infra"].value_counts().sort_index().items()
        },
    }
    assert asm.reference_dates == src_manifest["reference_dates"], "ride frames must share dates"

    out = new_ride_version(source, model_version())
    files, extra = _write_ride_files(out, asm, ride, feats, metrics)
    changed = verify_unchanged(source, out)
    if changed:
        raise RuntimeError(f"ride export changed walk/bundle files: {changed}")
    ride_summary = {
        "model": "cyclist crashes",
        "headline": metrics["headline"],
        "exposure": EXPOSURE,
        "exposure_detail": EXPOSURE_DETAIL,
        "temporal_model": choice,
        "segments": "same road segments and seg ids as walk",
        "spatial_train_years": [SPATIAL_FINAL.start, SPATIAL_FINAL.stop - 1],
    }
    register_ride(out, files, ride_summary, extra=extra)
    log.info("ride bundle %s | files %d | headline %s", out.name, len(files), metrics["headline"])


def link_main(version: str) -> None:
    target = ARTIFACTS_DIR / version
    if not (target / "manifest.json").exists():
        raise FileNotFoundError(f"no bundle at {target}")
    current = ARTIFACTS_DIR / "current"
    current.unlink()
    current.symlink_to(version)
    log.info("artifacts/current -> %s", version)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("features")
    sub.add_parser("export")
    link = sub.add_parser("link")
    link.add_argument("version")
    args = parser.parse_args()
    if args.cmd == "features":
        features_main()
    elif args.cmd == "export":
        export_main()
    else:
        link_main(args.version)


if __name__ == "__main__":
    main()
