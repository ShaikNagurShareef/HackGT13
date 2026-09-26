"""CLI: fit City Pulse, evaluate on a future year, and add hex artifacts to the current bundle.

Usage: uv run --package pathpulse-data python -m pathpulse_data.citywide.export

Hex log density = base + sum(spatial factors) + log(sum_g share_g * temporal_mult_g(cell)).
The temporal part is a mixture over road groups, so it is shown as one "Time and conditions"
factor; attribution stays exact because it telescopes over whatever factors are given.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
from datetime import date, datetime, time

import numpy as np
import pandas as pd

from pathpulse_data.citywide.features import GROUPS, HexData, build_hex_data
from pathpulse_data.citywide.model import benchmark_hex, fit_hex, hex_counts, hex_design
from pathpulse_data.config import ARTIFACTS_DIR, TZ
from pathpulse_data.export.assemble import CONDITIONS, DAY_GROUPS, reference_dates
from pathpulse_data.export.frames import build_quantiles, pack_frames, score_from_log_density
from pathpulse_data.model.temporal import CELL_KEYS, LEVELS
from pathpulse_data.model.temporal_data import cell_table, crash_cells, fit_final, load_hours
from pathpulse_data.timeseries.exposure import light_at

log = logging.getLogger(__name__)
HEX_FACTORS = {
    "history": "Pedestrian crash history in this area",
    "nearby": "Pedestrian crashes in surrounding areas",
    "vehicle_crashes": "Vehicle crashes in this area",
    "arterials": "Major roads",
    "streets": "Street network density",
    "traffic": "Traffic volume and speed",
    "activity": "Pedestrian activity and transit",
}
FEATURE_GROUP = {
    "km_arterial": "arterials",
    "km_collector": "arterials",
    "signals": "arterials",
    "km_local": "streets",
    "intersections": "streets",
    "log_aadt": "traffic",
    "log_aadt_missing": "traffic",
    "speed": "traffic",
    "speed_missing": "traffic",
    "log_ped_volume": "activity",
    "log_ped_volume_missing": "activity",
    "bus_stops": "activity",
    "log_boardings": "activity",
    "log_nonped": "vehicle_crashes",
    "log_nbr_ped": "nearby",
    "log_nbr_nonped": "nearby",
}
TEMPORAL_KEY, TEMPORAL_LABEL = "time_conditions", "Time of day and conditions"


def temporal_multipliers(t_ref: pd.DataFrame, tmodel: object) -> pd.DataFrame:
    """Normalized pedestrian multiplier per (road_group, day_group, hour, light, wet)."""
    grid = pd.DataFrame(
        itertools.product(
            LEVELS["road_group"], DAY_GROUPS, range(24), LEVELS["light"], (False, True)
        ),
        columns=list(CELL_KEYS),
    )
    mult = tmodel.normalized_multiplier(grid, reference=t_ref)  # type: ignore[attr-defined]
    return grid.assign(mult=mult.to_numpy())


def spatial_factors(
    fit: object, data: HexData, expected: pd.DataFrame
) -> tuple[pd.DataFrame, float]:
    x = hex_design(data, fit.train_years)  # type: ignore[attr-defined]
    contrib, base = fit.spf.contributions(x)  # type: ignore[attr-defined]
    out = pd.DataFrame(0.0, index=data.cells, columns=list(HEX_FACTORS))
    for col in contrib.columns:
        out[FEATURE_GROUP[col]] += contrib[col].to_numpy()
    out["history"] += np.log(expected["eb"].to_numpy() / expected["spf"].to_numpy())
    means = out.mean()
    return out - means, base + float(means.sum())


def hex_log_temporal(
    share: pd.DataFrame, mults: pd.DataFrame, key: tuple[str, int, str, bool]
) -> np.ndarray:
    dg, hour, light, wet = key
    sel = mults.loc[
        (mults["day_group"] == dg)
        & (mults["hour"] == hour)
        & (mults["light"] == light)
        & (mults["wet"] == wet)
    ].set_index("road_group")["mult"]
    mix = sum(share[g].to_numpy() * float(sel[g]) for g in GROUPS)
    return np.log(np.maximum(mix, 1e-12))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    data = build_hex_data()
    metrics = {
        "test": benchmark_hex(fit_hex(data, range(2020, 2024)), data, 2024),
        "validation": benchmark_hex(fit_hex(data, range(2020, 2023)), data, 2023),
    }
    fit = fit_hex(data, range(2020, 2025))
    expected = fit.expected(data)
    factors, base = spatial_factors(fit, data, expected)
    hours = load_hours()
    crashes = crash_cells(hours)
    t_years = range(2017, 2024)
    tmodel = fit_final(crashes, hours, t_years)
    t_ref = cell_table(crashes, hours, t_years).query("is_ped")[[*CELL_KEYS, "hours"]]
    mults = temporal_multipliers(t_ref, tmodel)

    refs = reference_dates(date.today())
    spatial_sum = base + factors.sum(axis=1).to_numpy()
    per_frame = {}
    for dg, cond in itertools.product(DAY_GROUPS, CONDITIONS):
        rows = []
        for h in range(24):
            light = light_at(datetime.combine(refs[dg], time(h, 30), TZ)).value
            rows.append(
                spatial_sum
                + hex_log_temporal(data.group_share, mults, (dg, h, light, CONDITIONS[cond]))
            )
        per_frame[f"{dg}_{cond}"] = np.asarray(rows)
    quantiles = build_quantiles(np.concatenate([v.ravel() for v in per_frame.values()]))
    write_bundle(data, factors, base, quantiles, per_frame, mults, expected, metrics)


def write_bundle(
    data: HexData,
    factors: pd.DataFrame,
    base: float,
    quantiles: np.ndarray,
    per_frame: dict[str, np.ndarray],
    mults: pd.DataFrame,
    expected: pd.DataFrame,
    metrics: dict[str, object],
) -> None:
    out = (ARTIFACTS_DIR / "current").resolve()
    for key, values in per_frame.items():
        (out / f"hex_frames_{key}.bin").write_bytes(
            pack_frames(score_from_log_density(values, quantiles)).tobytes()
        )
    np.save(out / "hex_factors.npy", factors.to_numpy(np.float32))
    total = hex_counts(data, range(2020, 2025), ped=False) + hex_counts(
        data, range(2020, 2025), ped=True
    )
    ped = hex_counts(data, range(2020, 2025), ped=True)
    confidence = np.where(total >= 30, "high", np.where(total >= 5, "medium", "limited"))
    hex_meta = {
        "cells": list(data.cells),
        "lat": data.centroids["lat"].round(6).tolist(),
        "lon": data.centroids["lon"].round(6).tolist(),
        "share": {g: data.group_share[g].round(4).tolist() for g in GROUPS},
        "crashes": total.round(1).tolist(),
        "ped_crashes": ped.round(1).tolist(),
        "confidence": confidence.tolist(),
        "base": base,
        "quantiles": quantiles.tolist(),
        "factors": [{"key": k, "label": v} for k, v in HEX_FACTORS.items()],
        "temporal": {"key": TEMPORAL_KEY, "label": TEMPORAL_LABEL},
        "multipliers": mults.assign(mult=mults["mult"].round(6)).to_dict(orient="list"),
        "metrics": metrics,
    }
    (out / "hex_meta.json").write_text(json.dumps(hex_meta, separators=(",", ":"), default=str))
    (out / "hex_cells.json").write_text(json.dumps(list(data.cells), separators=(",", ":")))
    manifest = json.loads((out / "manifest.json").read_text())
    for p in sorted(out.glob("hex_*")):
        manifest["files"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest["n_hexes"] = len(data.cells)
    (out / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    log.info(
        "City Pulse: %d hexes | 2024 %s", len(data.cells), json.dumps(metrics["test"]["methods"][0])
    )


if __name__ == "__main__":
    main()
