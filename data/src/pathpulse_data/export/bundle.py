"""CLI: evaluate honestly, fit final models, and write artifacts/<model_version>/.

Usage: uv run --package pathpulse-data python -m pathpulse_data.export.bundle
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import UTC, date, datetime
from typing import Any

from pathpulse_data.citywide import export as citywide_export
from pathpulse_data.config import ARTIFACTS_DIR, CORE_BBOX, INTERIM_DIR
from pathpulse_data.export import writers
from pathpulse_data.export.assemble import CONDITIONS, DAY_GROUPS, assemble
from pathpulse_data.model.benchmark import benchmark
from pathpulse_data.model.dataset import load_segment_data
from pathpulse_data.model.spatial import fit_spatial
from pathpulse_data.model.temporal import CELL_KEYS
from pathpulse_data.model.temporal_data import (
    cell_table,
    crash_cells,
    evaluate_temporal,
    fit_final,
    load_hours,
)
from pathpulse_data.network.coverage import city_polygon, outline_geojson

log = logging.getLogger(__name__)
SPATIAL_TEST = (range(2020, 2024), 2024)
SPATIAL_VAL = (range(2020, 2023), 2023)
SPATIAL_FINAL = range(2020, 2025)
# 2024-25 timed data comes from only two narrow layers, so the shipped model stops at 2023.
TEMPORAL_TRAIN, TEMPORAL_TEST, TEMPORAL_FINAL = (
    range(2017, 2022),
    range(2022, 2024),
    range(2017, 2024),
)


def model_version() -> str:
    sha = (
        subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - local build CLI
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or "nogit"
    )
    return f"pp-{datetime.now(UTC):%Y%m%d-%H%M}-{sha}"


def evaluate_all() -> dict[str, Any]:
    data = load_segment_data()
    test = benchmark(fit_spatial(data, SPATIAL_TEST[0]), data, SPATIAL_TEST[1])
    val = benchmark(fit_spatial(data, SPATIAL_VAL[0]), data, SPATIAL_VAL[1])
    hours = load_hours()
    temporal = evaluate_temporal(crash_cells(hours), hours, TEMPORAL_TRAIN, TEMPORAL_TEST)
    return {"spatial_test": test, "spatial_validation": val, "temporal_test": temporal}


def headline(metrics: dict[str, Any]) -> dict[str, Any]:
    methods = {m["method"]: m for m in metrics["spatial_test"]["methods"]}
    ours = methods["PathPulse (EB ensemble)"]
    hin = methods["City High Injury Network"]
    return {
        "capture_top10": ours["capture_top10"],
        "capture_top10_ci95": metrics["spatial_test"]["capture_top10_ci95"],
        "vs_random": ours["capture_top10"] / 0.10,
        "hin_capture_top10": hin["capture_top10"],
        "hin_length_share": metrics["spatial_test"]["hin_length_share"],
        "capture_at_hin_share": ours["capture_at_hin_share"],
        "hin_capture_at_own_share": hin["capture_at_hin_share"],
        "model_only_capture_top10": methods["Model only (SPF)"]["capture_top10"],
        "validation_gain_vs_count_only": (
            {m["method"]: m for m in metrics["spatial_validation"]["methods"]}[
                "PathPulse (EB ensemble)"
            ]["capture_top10"]
            - {m["method"]: m for m in metrics["spatial_validation"]["methods"]}[
                "Past crash count only"
            ]["capture_top10"]
        ),
        "gain_vs_count_only_ci95": metrics["spatial_test"]["capture_gain_vs_count_only_ci95"],
        "count_only_capture_top10": methods["Past crash count only"]["capture_top10"],
        "roc_auc": ours["roc_auc"],
        "temporal_deviance_reduction": metrics["temporal_test"]["deviance_reduction"],
        "temporal_reduction_vs_hour_day": metrics["temporal_test"][
            "deviance_reduction_vs_hour_day"
        ],
        "test_year": metrics["spatial_test"]["test_year"],
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    metrics = evaluate_all()
    data = load_segment_data()
    fit = fit_spatial(data, SPATIAL_FINAL)
    hours = load_hours()
    crashes = crash_cells(hours)
    tmodel = fit_final(crashes, hours, TEMPORAL_FINAL)
    t_ref = cell_table(crashes, hours, TEMPORAL_FINAL).query("is_ped")[[*CELL_KEYS, "hours"]]
    asm = assemble(fit, tmodel, t_ref, data, date.today())

    version = model_version()
    out = ARTIFACTS_DIR / version
    out.mkdir(parents=True, exist_ok=True)
    meta = writers.write_segments(out, asm)
    writers.write_factors(out, asm)
    writers.write_frames(out, asm)
    graph_stats = writers.write_walk_graph(out)
    n_hotspots = writers.write_hotspot_nodes(out)
    report = json.loads((INTERIM_DIR / "ingest_report.json").read_text())
    metrics |= {
        "headline": headline(metrics),
        "temporal_effects": asm.temporal_effects,
        "ingest": report,
    }
    writers._dump(out / "metrics.json", metrics)
    writers._dump(out / "coverage.geojson", outline_geojson())
    writers.write_manifest(
        out,
        {
            "model_version": version,
            "created_at": datetime.now(UTC).isoformat(),
            "data_through": report["data_through"],
            "n_segments": len(meta),
            "day_groups": list(DAY_GROUPS),
            "conditions": list(CONDITIONS),
            "reference_dates": asm.reference_dates,
            "frame_light": asm.frame_light,
            "coverage_bbox": [round(v, 5) for v in city_polygon().bounds],
            "coverage_name": "City of Atlanta",
            "focus_bbox": CORE_BBOX,
            "walk_graph": graph_stats,
            "hotspot_nodes": n_hotspots,
            "spatial_train_years": [SPATIAL_FINAL.start, SPATIAL_FINAL.stop - 1],
        },
    )
    current = ARTIFACTS_DIR / "current"
    if current.is_symlink() or current.exists():
        current.unlink() if current.is_symlink() else shutil.rmtree(current)
    current.symlink_to(version)
    log.info("bundle written: %s | headline %s", out, json.dumps(metrics["headline"]))
    citywide_export.main()  # City Pulse hexes join the same versioned bundle


if __name__ == "__main__":
    main()
