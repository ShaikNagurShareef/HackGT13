"""APD crimes against persons: fairness filters, Atlanta-local day parts, per-hex counts.

Output rows carry only a category, a timestamp, a day part, and coordinates that are
aggregated to H3 res-9 hexes before anything is exported (no points leave the pipeline).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from pathpulse_data.citywide.hexgrid import cells_for
from pathpulse_data.config import THRESHOLDS, TZ
from pathpulse_data.safety.dayparts import DAY_PART_KEYS, day_part_for_hour
from pathpulse_data.safety.sources import CRIME_CATEGORIES, EXCLUDED_LOCATIONS


def _valid_coords(lat: pd.Series, lon: pd.Series) -> pd.Series:
    west, south, east, north = THRESHOLDS.georgia_bounds
    return lat.between(south, north) & lon.between(west, east)


def clean_crimes(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep persons-category offenses in public-facing places with usable coordinates.

    APD stores OccurredFromDate as true UTC epoch milliseconds (the hour profile only has
    its expected pre-dawn trough after conversion), so it is converted to Atlanta time.
    """
    keep = (
        raw["NIBRS_Offense"].isin(CRIME_CATEGORIES)
        & ~raw["LocationType"].isin(EXCLUDED_LOCATIONS)
        & raw["OccurredFromDate"].notna()
        & _valid_coords(raw["lat"], raw["lon"])
    )
    rows = raw.loc[keep]
    occurred = pd.to_datetime(rows["OccurredFromDate"], unit="ms", utc=True).dt.tz_convert(TZ)
    return pd.DataFrame(
        {
            "category": rows["NIBRS_Offense"].map(CRIME_CATEGORIES).to_numpy(),
            "occurred": occurred.to_numpy(),
            "day_part": [day_part_for_hour(h) for h in occurred.dt.hour],
            "lat": rows["lat"].to_numpy(float),
            "lon": rows["lon"].to_numpy(float),
        }
    ).assign(occurred=lambda f: pd.to_datetime(f["occurred"], utc=True).dt.tz_convert(TZ))


def in_window(crimes: pd.DataFrame, end: date, days: int) -> pd.DataFrame:
    """Crimes that occurred in the `days` days up to and including `end` (Atlanta dates)."""
    local_day = crimes["occurred"].dt.date
    return crimes.loc[(local_day > end - timedelta(days=days)) & (local_day <= end)]


def hex_counts(crimes: pd.DataFrame, cells: pd.Index) -> pd.DataFrame:
    """Crime counts per hex (rows, aligned to `cells`) and day part (columns)."""
    frame = pd.DataFrame(
        {"cell": cells_for(crimes["lat"], crimes["lon"]), "day_part": crimes["day_part"]}
    )
    table = pd.crosstab(frame["cell"], frame["day_part"]) if len(frame) else pd.DataFrame()
    out = table.reindex(index=cells, columns=list(DAY_PART_KEYS), fill_value=0)
    return out.fillna(0).astype(np.int64)
