"""CLI: load segments, snapped timed crashes, and the risk grid into Tiger Data.

Usage: DATABASE_URL=... uv run --package pathpulse-data python -m pathpulse_data.db.load_tiger
The demo never depends on this database; it is the system of record for history queries.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

from pathpulse_data.config import ARTIFACTS_DIR, DATA_DIR, INTERIM_DIR, REPO_ROOT

log = logging.getLogger(__name__)
SCHEMA = DATA_DIR / "sql" / "schema.sql"
HOURS = 24


def _copy_rows(cur: psycopg.Cursor, sql: str, rows: list[tuple[object, ...]]) -> None:
    with cur.copy(sql) as copy:
        for row in rows:
            copy.write_row(row)


def load_segments(cur: psycopg.Cursor) -> int:
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").sort_values("seg_id")
    names = segs["name"].astype("string").str.split(";").str[0].fillna("Unnamed street")
    cur.execute("TRUNCATE crashes; DELETE FROM segments;")
    rows = [
        (int(sid), str(n), str(g), float(length), geom.wkt)
        for sid, n, g, length, geom in zip(
            segs["seg_id"], names, segs["road_group"], segs["length"], segs.geometry, strict=True
        )
    ]
    _copy_rows(
        cur,
        "COPY segments (seg_id, name, road_group, length_m, geom) FROM STDIN",
        [(*r[:4], f"SRID=4326;{r[4]}") for r in rows],
    )
    return len(rows)


def _text(value: object) -> str | None:
    """Missing values arrive as NaN floats; COPY needs NULL."""
    return None if pd.isna(value) else str(value)


def load_crashes(cur: psycopg.Cursor) -> int:
    snaps = pd.read_parquet(INTERIM_DIR / "crash_segments.parquet")
    timed = snaps.loc[snaps["stream"] == "timed"]
    meta = pd.read_parquet(
        INTERIM_DIR / "crashes_timed.parquet",
        columns=["crash_id", "light_report", "surface_report", "lat", "lon"],
    )
    rows = timed.merge(meta, on="crash_id").dropna(subset=["ts"])
    _copy_rows(
        cur,
        "COPY crashes (ts, crash_id, seg_id, weight, is_ped, severity, light, surface, geom) "
        "FROM STDIN",
        [
            (
                r.ts,
                r.crash_id,
                int(r.seg_id),
                float(r.weight),
                bool(r.is_ped),
                _text(r.severity),
                _text(r.light_report),
                _text(r.surface_report),
                f"SRID=4326;POINT({r.lon} {r.lat})",
            )
            for r in rows.itertuples()
        ],
    )
    return len(rows)


def load_risk_grid(cur: psycopg.Cursor, bundle: Path) -> int:
    version = bundle.resolve().name
    cur.execute("DELETE FROM risk_grid WHERE model_version = %s", (version,))
    total = 0
    for path in sorted(bundle.glob("frames_*_*.bin")):
        day, cond = path.stem.removeprefix("frames_").split("_")
        frames = np.frombuffer(path.read_bytes(), dtype=np.uint8).reshape(HOURS, -1)
        rows = [
            (version, seg, day, cond, hour, int(frames[hour, seg]))
            for hour in range(HOURS)
            for seg in range(frames.shape[1])
        ]
        _copy_rows(
            cur,
            "COPY risk_grid (model_version, seg_id, day_group, cond, hour, score) FROM STDIN",
            rows,
        )
        total += len(rows)
    return total


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    load_dotenv(REPO_ROOT / "backend" / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        log.error("DATABASE_URL is not set (backend/.env)")
        return 1
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA.read_text())
        conn.commit()
        n_seg = load_segments(cur)
        n_crash = load_crashes(cur)
        n_grid = load_risk_grid(cur, ARTIFACTS_DIR / "current")
        conn.commit()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CALL refresh_continuous_aggregate('crashes_hourly', NULL, NULL)")
    log.info("loaded segments=%d crash rows=%d risk grid rows=%d", n_seg, n_crash, n_grid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
