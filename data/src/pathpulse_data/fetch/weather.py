"""CLI: hourly precipitation history from the Open-Meteo archive (no key, CC-BY 4.0)."""

from __future__ import annotations

import logging

import httpx
import pandas as pd

from pathpulse_data.config import CITY_LAT, CITY_LON, RAW_DIR, TZ

log = logging.getLogger(__name__)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2013-01-01", "2025-12-31"


def fetch_hourly(start: str = START, end: str = END) -> pd.DataFrame:
    params = {
        "latitude": CITY_LAT,
        "longitude": CITY_LON,
        "start_date": start,
        "end_date": end,
        "hourly": "precipitation,rain,snowfall,visibility",
        "timezone": "America/New_York",
    }
    resp = httpx.get(ARCHIVE_URL, params=params, timeout=120.0)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    times = pd.to_datetime(hourly["time"])
    # Open-Meteo returns local wall-clock times; DST gaps/repeats resolved by shifting.
    local = times.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")
    frame = pd.DataFrame(
        {
            "time": local,
            "precip_mm": hourly["precipitation"],
            "snow_cm": hourly["snowfall"],
        }
    )
    return frame.dropna(subset=["time"]).reset_index(drop=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frame = fetch_hourly()
    frame.to_parquet(RAW_DIR / "weather_hourly.parquet", index=False)
    log.info("weather hours=%d wet_share=%.3f", len(frame), float((frame.precip_mm >= 0.1).mean()))


if __name__ == "__main__":
    main()
