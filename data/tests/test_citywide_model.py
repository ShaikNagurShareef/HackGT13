"""City Pulse hex model: counts, design matrix, SPF + EB fit, and future-year benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.citywide.features import HexData
from pathpulse_data.citywide.hexgrid import neighbor_sum
from pathpulse_data.citywide.model import HexFit, benchmark_hex, hex_counts, hex_design
from pathpulse_data.model.spatial import K_GRID

from tests.conftest import synthetic_hex_data

DESIGN_COLUMNS = {
    "km_arterial",
    "km_collector",
    "km_local",
    "intersections",
    "signals",
    "bus_stops",
    "log_aadt",
    "log_aadt_missing",
    "speed",
    "speed_missing",
    "log_ped_volume",
    "log_ped_volume_missing",
    "log_boardings",
    "log_nonped",
    "log_nbr_ped",
    "log_nbr_nonped",
}


def _tiny_data(crashes: pd.DataFrame) -> HexData:
    base = synthetic_hex_data()
    return HexData(
        cells=base.cells,
        features=base.features,
        crashes=crashes,
        group_share=base.group_share,
        blocks=base.blocks,
        centroids=base.centroids,
    )


@pytest.mark.unit
def test_hex_counts_filters_years_and_type_and_sums_weights() -> None:
    cells = synthetic_hex_data().cells
    a, b = cells[0], cells[1]
    crashes = pd.DataFrame(
        {
            "cell": [a, a, a, b, b],
            "year": [2020, 2021, 2019, 2020, 2020],
            "is_ped": [True, True, True, False, True],
            "weight": [1.0, 0.5, 9.0, 4.0, 2.0],
        }
    )
    data = _tiny_data(crashes)

    ped = hex_counts(data, range(2020, 2022), ped=True)
    nonped = hex_counts(data, range(2020, 2022), ped=False)

    assert ped.index.equals(cells)
    assert ped[a] == 1.5  # 2019 row is outside the window
    assert ped[b] == 2.0
    assert nonped[b] == 4.0
    assert ped.drop([a, b]).eq(0.0).all()


@pytest.mark.unit
def test_hex_counts_empty_crash_table_is_all_zero() -> None:
    empty = pd.DataFrame({"cell": [], "year": [], "is_ped": [], "weight": []})
    data = _tiny_data(empty.astype({"year": int, "is_ped": bool, "weight": float}))

    counts = hex_counts(data, range(2019, 2024), ped=True)

    assert len(counts) == len(data.cells)
    assert counts.sum() == 0.0


@pytest.mark.unit
def test_hex_design_imputes_missing_and_uses_per_year_history() -> None:
    data = synthetic_hex_data()
    years = range(2019, 2023)
    f = data.features

    x = hex_design(data, years)

    assert set(x.columns) == DESIGN_COLUMNS
    assert x.index.equals(data.cells)
    assert not x.isna().any().any()
    for col in ("log_aadt", "speed", "log_ped_volume"):
        missing = f[col].isna()
        assert (x[f"{col}_missing"] == missing.astype(float)).all()
        assert (x.loc[missing, col] == f[col].median()).all()
    nonped = hex_counts(data, years, ped=False)
    ped = hex_counts(data, years, ped=True)
    np.testing.assert_allclose(x["log_nonped"], np.log1p(nonped / len(years)))
    np.testing.assert_allclose(x["log_nbr_ped"], np.log1p(neighbor_sum(ped) / len(years)))


@pytest.mark.integration
def test_fit_hex_expected_is_positive_and_eb_blends_history(
    hex_fitted: tuple[HexData, HexFit],
) -> None:
    data, fit = hex_fitted

    exp = fit.expected(data)

    assert list(exp.columns) == ["spf", "eb", "history"]
    assert exp.index.equals(data.cells)
    assert (exp["spf"] > 0).all()
    assert (exp["eb"] > 0).all()
    assert fit.k in K_GRID
    assert 0.0 <= fit.spf.weight_lgbm <= 1.0
    np.testing.assert_array_equal(
        exp["history"], hex_counts(data, fit.train_years, ped=True).to_numpy()
    )
    # EB annual rate lies between the model's rate and the observed annual history.
    n = len(fit.train_years)
    lo = np.minimum(exp["spf"], exp["history"] / n) - 1e-9
    hi = np.maximum(exp["spf"], exp["history"] / n) + 1e-9
    assert ((exp["eb"] >= lo) & (exp["eb"] <= hi)).all()


@pytest.mark.integration
def test_fit_hex_ranks_high_rate_cells_above_low_rate_cells(
    hex_fitted: tuple[HexData, HexFit],
) -> None:
    data, fit = hex_fitted
    arterial = data.features["km_arterial"]

    exp = fit.expected(data)
    top = exp.loc[arterial >= arterial.quantile(0.8), "spf"].mean()
    bottom = exp.loc[arterial <= arterial.quantile(0.2), "spf"].mean()

    assert top > 1.5 * bottom


@pytest.mark.integration
def test_benchmark_hex_reports_three_methods_deterministically(
    hex_fitted: tuple[HexData, HexFit],
) -> None:
    data, fit = hex_fitted

    first = benchmark_hex(fit, data, 2023)
    second = benchmark_hex(fit, data, 2023)

    assert first == second
    assert first["test_year"] == 2023
    assert first["n_hexes"] == len(data.cells)
    assert first["observed_ped_crashes"] == hex_counts(data, range(2023, 2024), ped=True).sum()
    methods = {row["method"]: row for row in first["methods"]}  # type: ignore[attr-defined]
    assert set(methods) == {"City Pulse (EB ensemble)", "Past crash count only", "Random"}
    for row in methods.values():
        assert 0.0 <= row["capture_top10"] <= 1.0
        assert 0.0 <= row["roc_auc"] <= 1.0
        assert 0.0 <= row["pr_auc"] <= 1.0
    assert methods["City Pulse (EB ensemble)"]["roc_auc"] > methods["Random"]["roc_auc"]
