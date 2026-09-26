"""Help points: OSM + GT call boxes normalized to kinds, deduped, counted, and distanced."""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest
from pathpulse_data.safety.helppoints import (
    HELP_KINDS,
    callbox_points,
    dedupe_points,
    hex_help_counts,
    nearest_distance_m,
    osm_help_points,
)

LAT, LON = 33.7756, -84.3963


def _osm(rows: list[dict[str, object]]) -> pd.DataFrame:
    base = {"amenity": None, "railway": None, "highway": None, "network": None, "operator": None}
    return pd.DataFrame([{**base, "name": None, "lat": LAT, "lon": LON, **r} for r in rows])


@pytest.mark.unit
def test_osm_help_points_classify_kinds_and_skip_lamps() -> None:
    raw = _osm(
        [
            {"amenity": "police", "name": "APD Zone 5"},
            {"amenity": "fire_station", "name": None},
            {"amenity": "hospital", "name": "Grady"},
            {"railway": "station", "network": "MARTA", "name": "North Avenue"},
            {"railway": "station", "operator": "Amtrak", "name": "Peachtree"},  # not MARTA
            {"highway": "street_lamp"},
        ]
    )

    out = osm_help_points(raw)

    assert list(out["kind"]) == ["police", "fire", "hospital", "marta"]
    assert out.loc[out["kind"] == "fire", "name"].iloc[0] == "Fire station"
    assert set(out["kind"]) <= set(HELP_KINDS)


@pytest.mark.unit
def test_callbox_points_keep_active_outdoor_boxes_only() -> None:
    raw = pd.DataFrame(
        {
            "phone_name": ["Ferst and Fowler ", "Library lobby", "Tech Green", None],
            "phone_status": ["Active", "Active", "Inactive", "Active"],
            "location_code": ["Outside", "Inside", "Outside", "Outside"],
            "lat": [LAT] * 4,
            "lon": [LON] * 4,
        }
    )

    out = callbox_points(raw)

    assert list(out["kind"]) == ["blue_light", "blue_light"]
    assert list(out["name"]) == ["Ferst and Fowler", "Emergency call box"]


@pytest.mark.unit
def test_dedupe_points_merges_same_kind_within_radius() -> None:
    pts = pd.DataFrame(
        {
            "kind": ["hospital", "hospital", "police"],
            "name": ["Grady", "Grady ER", "APD"],
            "lat": [LAT, LAT + 0.0001, LAT],
            "lon": [LON, LON, LON],
        }
    )

    out = dedupe_points(pts, radius_m=30.0)

    assert sorted(out["kind"]) == ["hospital", "police"]


@pytest.mark.unit
def test_hex_help_counts_and_nearest_distance() -> None:
    cell = h3.latlng_to_cell(LAT, LON, 9)
    pts = pd.DataFrame(
        {"kind": ["police", "fire"], "name": ["a", "b"], "lat": [LAT] * 2, "lon": [LON] * 2}
    )

    counts = hex_help_counts(pts, pd.Index([cell]))
    dist = nearest_distance_m(np.array([[LON, LAT + 0.001]]), pts[["lon", "lat"]].to_numpy())

    assert counts.loc[cell] == 2
    assert dist[0] == pytest.approx(111.3, abs=1.0)


@pytest.mark.unit
def test_nearest_distance_without_points_is_nan() -> None:
    dist = nearest_distance_m(np.array([[LON, LAT]]), np.empty((0, 2)))

    assert np.isnan(dist[0])
