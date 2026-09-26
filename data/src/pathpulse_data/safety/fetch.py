"""CLI: pull raw safety-signal layers into data/raw/ (gitignored, re-fetchable).

Usage: uv run --package pathpulse-data python -m pathpulse_data.safety.fetch

- APD crimes against persons for the last 24 months (12 shipped + 12 for stable banding).
- Georgia Tech emergency call boxes.
- OpenStreetMap police, fire stations, hospitals, rail stations, and street lamps.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import osmnx as ox
import pandas as pd

from pathpulse_data.config import RAW_DIR
from pathpulse_data.fetch.arcgis import fetch_layer
from pathpulse_data.network.coverage import buffered_polygon
from pathpulse_data.safety.sources import CALLBOX_LAYER, OSM_TAGS, crime_layer

log = logging.getLogger(__name__)
WINDOW_DAYS = 730
OSM_KEEP = ("amenity", "railway", "highway", "station", "network", "operator", "name")


def fetch_crimes(today: date) -> pd.DataFrame:
    start = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    raw = fetch_layer(crime_layer(start))
    return raw[["OccurredFromDate", "NIBRS_Offense", "LocationType", "lon", "lat"]]


def fetch_osm() -> pd.DataFrame:
    feats = ox.features.features_from_polygon(buffered_polygon(), OSM_TAGS)
    points = feats.geometry.representative_point()
    cols = [c for c in OSM_KEEP if c in feats.columns]
    out = pd.DataFrame(feats[cols].astype("string")).reset_index()
    return out.assign(lon=points.x.to_numpy(), lat=points.y.to_numpy()).astype(
        {"element": "string", "id": "int64"}
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    crimes = fetch_crimes(date.today())
    crimes.to_parquet(RAW_DIR / "safety_apd_crime.parquet")
    boxes = fetch_layer(CALLBOX_LAYER)
    boxes.to_parquet(RAW_DIR / "safety_gt_callboxes.parquet")
    osm = fetch_osm()
    osm.to_parquet(RAW_DIR / "safety_osm.parquet")
    log.info("safety raw: crimes=%d callboxes=%d osm=%d", len(crimes), len(boxes), len(osm))


if __name__ == "__main__":
    main()
