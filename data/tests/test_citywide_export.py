"""City Pulse export: temporal mixing, centered spatial factors, and the hex bundle files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.citywide import export
from pathpulse_data.citywide.export import (
    HEX_FACTORS,
    hex_log_temporal,
    spatial_factors,
    temporal_multipliers,
    write_bundle,
)
from pathpulse_data.citywide.features import GROUPS, HexData
from pathpulse_data.citywide.model import HexFit
from pathpulse_data.export.frames import N_QUANTILES
from pathpulse_data.model.temporal import CELL_KEYS, LEVELS

N_GRID = len(LEVELS["road_group"]) * len(LEVELS["day_group"]) * 24 * len(LEVELS["light"]) * 2
GROUP_MULT = {"arterial": 2.0, "collector": 1.0, "local": 0.5}


class _StubTemporal:
    """Multiplier depends only on road group and wet flag; records the reference it saw."""

    def __init__(self) -> None:
        self.reference: pd.DataFrame | None = None

    def normalized_multiplier(self, cells: pd.DataFrame, reference: pd.DataFrame) -> pd.Series:
        self.reference = reference
        wet = np.where(cells["wet"], 1.5, 1.0)
        return pd.Series(cells["road_group"].map(GROUP_MULT).to_numpy() * wet, index=cells.index)


def _mults() -> pd.DataFrame:
    return temporal_multipliers(pd.DataFrame({"hours": [1.0]}), _StubTemporal())


@pytest.mark.unit
def test_temporal_multipliers_cover_full_cell_grid() -> None:
    stub = _StubTemporal()
    ref = pd.DataFrame({"hours": [1.0]})

    mults = temporal_multipliers(ref, stub)

    assert list(mults.columns) == [*CELL_KEYS, "mult"]
    assert len(mults) == N_GRID
    assert not mults.duplicated(subset=list(CELL_KEYS)).any()
    assert set(mults["hour"]) == set(range(24))
    assert stub.reference is ref
    wet_art = mults.loc[(mults["road_group"] == "arterial") & mults["wet"], "mult"]
    assert (wet_art == 3.0).all()


@pytest.mark.unit
def test_hex_log_temporal_mixes_group_multipliers_by_road_share() -> None:
    share = pd.DataFrame(
        {"arterial": [1.0, 0.5, 0.0], "collector": [0.0, 0.5, 0.0], "local": [0.0, 0.0, 1.0]}
    )

    dry = hex_log_temporal(share, _mults(), ("weekday", 8, "day", False))
    wet = hex_log_temporal(share, _mults(), ("weekday", 8, "day", True))

    np.testing.assert_allclose(dry, np.log([2.0, 1.5, 0.5]))
    np.testing.assert_allclose(wet - dry, np.log(1.5))


@pytest.mark.unit
def test_hex_log_temporal_floors_empty_mix() -> None:
    share = pd.DataFrame({g: [0.0] for g in GROUPS})

    out = hex_log_temporal(share, _mults(), ("sunday", 2, "dark", False))

    np.testing.assert_allclose(out, np.log(1e-12))


@pytest.mark.integration
def test_spatial_factors_are_centered_and_reconstruct_eb_log_rate(
    hex_fitted: tuple[HexData, HexFit],
) -> None:
    data, fit = hex_fitted
    expected = fit.expected(data)

    factors, base = spatial_factors(fit, data, expected)

    assert list(factors.columns) == list(HEX_FACTORS)
    assert factors.index.equals(data.cells)
    np.testing.assert_allclose(factors.mean().to_numpy(), 0.0, atol=1e-9)
    np.testing.assert_allclose(
        base + factors.sum(axis=1).to_numpy(), np.log(expected["eb"].to_numpy()), atol=1e-6
    )
    # History factor is exactly the EB-over-SPF log lift (up to its centering constant).
    lift = np.log(expected["eb"] / expected["spf"])
    np.testing.assert_allclose(factors["history"], lift - lift.mean(), atol=1e-9)


def _three_hex_data() -> HexData:
    cells = pd.Index(["89a", "89b", "89c"], name="cell")
    # 2020-2024 totals: 30 (high), 5 (medium), 4 (limited); 2019 rows fall outside the window.
    counts = {"89a": (20, 10), "89b": (2, 3), "89c": (4, 0)}
    rows = [
        {"cell": c, "year": 2021, "is_ped": ped, "weight": 1.0}
        for c, (nonped_n, ped_n) in counts.items()
        for ped, k in ((False, nonped_n), (True, ped_n))
        for _ in range(k)
    ]
    rows.append({"cell": "89c", "year": 2019, "is_ped": True, "weight": 1.0})
    return HexData(
        cells=cells,
        features=pd.DataFrame(index=cells),
        crashes=pd.DataFrame(rows),
        group_share=pd.DataFrame(
            {"arterial": [1.0, 0.2, 0.0], "collector": [0.0, 0.3, 0.0], "local": [0.0, 0.5, 1.0]},
            index=cells,
        ),
        blocks=pd.Series(["b"] * 3, index=cells),
        centroids=pd.DataFrame(
            {"lat": [33.7512345, 33.76, 33.77], "lon": [-84.3912345, -84.40, -84.41]},
            index=cells,
        ),
    )


@pytest.mark.unit
def test_write_bundle_writes_hex_files_and_updates_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "current"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps({"model_version": "t", "files": {"a": "x"}}))
    monkeypatch.setattr(export, "ARTIFACTS_DIR", tmp_path)
    data = _three_hex_data()
    factors = pd.DataFrame(0.1, index=data.cells, columns=list(HEX_FACTORS))
    frames = {"weekday_dry": np.tile(np.array([-3.0, -2.0, -1.0]), (24, 1))}
    quantiles = np.linspace(-3.0, -1.0, N_QUANTILES)  # uniform: log density -2 scores 50
    metrics = {"test": {"methods": [{"method": "City Pulse (EB ensemble)"}]}}

    write_bundle(data, factors, -2.5, quantiles, frames, _mults(), pd.DataFrame(), metrics)

    buf = np.frombuffer((out / "hex_frames_weekday_dry.bin").read_bytes(), dtype=np.uint8)
    assert buf.shape == (24 * 3,)
    assert buf[:3].tolist() == [0, 50, 100]
    stored = np.load(out / "hex_factors.npy")
    assert stored.shape == (3, len(HEX_FACTORS))
    assert stored.dtype == np.float32
    meta = json.loads((out / "hex_meta.json").read_text())
    assert meta["cells"] == ["89a", "89b", "89c"]
    assert meta["lat"][0] == 33.751234
    assert meta["crashes"] == [30.0, 5.0, 4.0]
    assert meta["ped_crashes"] == [10.0, 3.0, 0.0]
    assert meta["confidence"] == ["high", "medium", "limited"]
    assert meta["base"] == -2.5
    assert [f["key"] for f in meta["factors"]] == list(HEX_FACTORS)
    assert set(meta["share"]) == set(GROUPS)
    assert len(meta["multipliers"]["mult"]) == N_GRID
    assert json.loads((out / "hex_cells.json").read_text()) == meta["cells"]
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["model_version"] == "t"
    assert manifest["n_hexes"] == 3
    assert manifest["files"]["a"] == "x"
    for name in ("hex_frames_weekday_dry.bin", "hex_factors.npy", "hex_meta.json"):
        assert manifest["files"][name] == hashlib.sha256((out / name).read_bytes()).hexdigest()
