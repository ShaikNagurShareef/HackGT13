"""The safety layer is optional: partial raw pulls must skip it, never break the bundle."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.safety import export as safety_export
from pathpulse_data.safety.activity import activity_thresholds


def _touch(raw: Path, *names: str) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    for name in names:
        (raw / name).write_bytes(b"")


@pytest.mark.unit
@pytest.mark.parametrize(
    "present",
    [
        (),
        ("safety_apd_crime.parquet",),
        ("safety_apd_crime.parquet", "safety_osm.parquet"),
        ("safety_apd_crime.parquet", "safety_gt_callboxes.parquet"),
    ],
)
def test_partial_raw_pulls_skip_the_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    present: tuple[str, ...],
) -> None:
    raw = tmp_path / "raw"
    _touch(raw, *present)
    monkeypatch.setattr(safety_export, "RAW_DIR", raw)
    monkeypatch.setattr(safety_export, "build", lambda out: pytest.fail("build must not run"))

    with caplog.at_level(logging.WARNING):
        safety_export.add_safety(tmp_path / "bundle")

    assert "safety" in caplog.text


@pytest.mark.unit
def test_build_failure_is_logged_and_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    raw = tmp_path / "raw"
    _touch(raw, *safety_export.REQUIRED_RAW)
    monkeypatch.setattr(safety_export, "RAW_DIR", raw)

    def boom(out: Path) -> dict[str, object]:
        raise FileNotFoundError("streetlight source missing")

    monkeypatch.setattr(safety_export, "build", boom)
    monkeypatch.setattr(safety_export, "write_safety", lambda *a: pytest.fail("nothing to write"))

    with caplog.at_level(logging.WARNING):
        safety_export.add_safety(tmp_path / "bundle")

    assert "streetlight source missing" in caplog.text


@pytest.mark.unit
def test_activity_thresholds_explain_missing_streetlight_data() -> None:
    rates = pd.DataFrame({"night": [np.nan, np.nan], "morning": [np.nan, np.inf]})

    with pytest.raises(RuntimeError, match="no StreetLight activity"):
        activity_thresholds(rates)
