"""Paginated ArcGIS FeatureServer client that snapshots layers to parquet."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from pathpulse_data.config import Layer

log = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 2000
TIMEOUT_S = 60.0


def build_params(layer: Layer, offset: int, page_size: int) -> dict[str, str]:
    params = {
        "where": layer.where,
        "outFields": layer.out_fields,
        "outSR": "4326",
        "returnGeometry": "true" if layer.geometry else "false",
        "resultOffset": str(offset),
        "resultRecordCount": str(page_size),
        "orderByFields": layer.order_by,
        "f": "json",
    }
    if layer.bbox is not None:
        params |= {
            "geometry": ",".join(str(v) for v in layer.bbox),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        }
    return params


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=20), reraise=True)
def _get_page(client: httpx.Client, url: str, params: dict[str, str]) -> dict[str, Any]:
    resp = client.get(f"{url}/query", params=params)
    resp.raise_for_status()
    payload: dict[str, Any] = resp.json()
    if "error" in payload:
        raise RuntimeError(f"ArcGIS error for {url}: {payload['error'].get('message')}")
    return payload


def _flatten(feature: dict[str, Any]) -> dict[str, Any]:
    row = dict(feature.get("attributes", {}))
    geom = feature.get("geometry") or {}
    if "x" in geom and "y" in geom:
        row["lon"], row["lat"] = geom["x"], geom["y"]
    elif "paths" in geom:
        row["paths"] = geom["paths"]
    elif "rings" in geom:
        row["rings"] = geom["rings"]
    return row


def fetch_layer(layer: Layer, page_size: int = DEFAULT_PAGE_SIZE) -> pd.DataFrame:
    """Fetch every feature of a layer, following ArcGIS transfer-limit pagination."""
    rows: list[dict[str, Any]] = []
    offset = 0
    with httpx.Client(timeout=TIMEOUT_S) as client:
        while True:
            payload = _get_page(client, layer.url, build_params(layer, offset, page_size))
            features = payload.get("features", [])
            rows.extend(_flatten(f) for f in features)
            offset += len(features)
            if not features or not payload.get("exceededTransferLimit"):
                break
    log.info("fetched %s: %d rows", layer.key, len(rows))
    return pd.DataFrame(rows)
