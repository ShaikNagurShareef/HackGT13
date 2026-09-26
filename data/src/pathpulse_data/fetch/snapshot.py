"""CLI: snapshot every configured ArcGIS layer and StreetLight zone to data/raw/*.parquet.

Usage: uv run --package pathpulse-data python -m pathpulse_data.fetch.snapshot [key ...]
"""

from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from pathpulse_data.config import LAYERS, RAW_DIR, STREETLIGHT_ZONES, Layer, streetlight_url
from pathpulse_data.fetch.arcgis import fetch_layer

log = logging.getLogger(__name__)
MAX_WORKERS = 6


def _serialize_geometry(df: pd.DataFrame) -> pd.DataFrame:
    """Parquet cannot store ragged nested lists reliably; keep them as JSON strings."""
    out = df.copy()
    for col in ("paths", "rings"):
        if col in out.columns:
            out[col] = out[col].map(lambda v: json.dumps(v) if v is not None else None)
    return out


def _ring_centroid(rings_json: str | None) -> tuple[float, float]:
    if not rings_json:
        return (np.nan, np.nan)
    ring = np.asarray(json.loads(rings_json)[0], dtype=float)
    return (float(ring[:, 0].mean()), float(ring[:, 1].mean()))


def snapshot_layer(layer: Layer) -> tuple[str, int]:
    df = _serialize_geometry(fetch_layer(layer))
    df.to_parquet(RAW_DIR / f"{layer.key}.parquet", index=False)
    return layer.key, len(df)


def snapshot_streetlight(zone: str) -> tuple[str, int]:
    """Hex footprints once (All Days / All Day) + all day-type x day-part volumes."""
    url = streetlight_url(zone)
    geom = fetch_layer(
        Layer(
            f"sl_geom_{zone}",
            url,
            where="Day_Type LIKE '0:%' AND Day_Part LIKE '0:%'",
            bbox=None,
            out_fields="Zone_ID",
        )
    )
    geom = _serialize_geometry(geom)
    cents = geom["rings"].map(_ring_centroid)
    geom = geom.assign(lon=[c[0] for c in cents], lat=[c[1] for c in cents])[
        ["Zone_ID", "lon", "lat"]
    ]
    vols = fetch_layer(
        Layer(
            f"sl_vol_{zone}",
            url,
            bbox=None,
            geometry=False,
            out_fields="Zone_ID,Day_Type,Day_Part,Average_Daily_Zone_Traffic__StL",
        )
    )
    merged = vols.merge(geom, on="Zone_ID", how="left")
    key = f"streetlight_{zone.split('_')[0].lower()}"
    merged.to_parquet(RAW_DIR / f"{key}.parquet", index=False)
    return key, len(merged)


def main(keys: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    layers = [lyr for lyr in LAYERS if not keys or lyr.key in keys]
    zones = [z for z in STREETLIGHT_ZONES if not keys or "streetlight" in keys]
    failures = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(snapshot_layer, lyr): lyr.key for lyr in layers}
        futures |= {pool.submit(snapshot_streetlight, z): z for z in zones}
        for fut in as_completed(futures):
            try:
                key, n = fut.result()
                log.info("OK   %-28s %8d rows", key, n)
            except Exception:  # report every failure, keep the rest of the snapshot
                failures += 1
                log.exception("FAIL %s", futures[fut])
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
