"""Ride model: the walk model family retargeted to cyclist crashes, walk behavior unchanged."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pathpulse_data.export.factors import WALK_SPEC, decompose
from pathpulse_data.model.dataset import SegmentData, design_matrix, window_counts
from pathpulse_data.model.spatial import fit_spatial
from pathpulse_data.model.temporal import FACTOR_GROUPS
from pathpulse_data.model.temporal_data import as_target
from pathpulse_data.ride.features import RIDE_EXTRA_COLUMNS
from pathpulse_data.ride.spec import RIDE_SPEC

from tests.conftest import _synthetic_data


def _with_bikes(data: SegmentData, seed: int = 1) -> SegmentData:
    """Relabel a random 30% of non-pedestrian crashes as cyclist crashes; add ride extras."""
    rng = np.random.default_rng(seed)
    crashes = data.crashes.assign(
        is_bike=(~data.crashes["is_ped"]) & (rng.random(len(data.crashes)) < 0.3)
    )
    n = len(data.features)
    extra = pd.DataFrame(
        {
            "bike_protected": (rng.random(n) < 0.1).astype(float),
            "bike_painted": (rng.random(n) < 0.1).astype(float),
            "bike_shared": (rng.random(n) < 0.1).astype(float),
            "beltline_adjacent": (rng.random(n) < 0.02).astype(float),
            "log_bike_activity": np.log1p(rng.poisson(20, n)).astype(float),
        },
        index=data.features.index,
    )
    return replace(data, crashes=crashes, target_col="is_bike", extra=extra)


@pytest.fixture(scope="module")
def walk_data() -> SegmentData:
    return _synthetic_data()[0]


@pytest.mark.unit
def test_segment_data_defaults_to_the_pedestrian_target(walk_data: SegmentData) -> None:
    assert walk_data.target_col == "is_ped"
    assert walk_data.extra is None


@pytest.mark.unit
def test_window_counts_follow_the_target_column(walk_data: SegmentData) -> None:
    ride = _with_bikes(walk_data)
    years = range(2019, 2021)
    sel = ride.crashes.loc[ride.crashes["year"].isin(list(years))]

    bikes = window_counts(ride, years, ped=True)
    others = window_counts(ride, years, ped=False)

    assert bikes.sum() == pytest.approx(sel["is_bike"].sum())
    assert others.sum() == pytest.approx((~sel["is_bike"]).sum())
    assert window_counts(walk_data, years, ped=True).sum() == pytest.approx(sel["is_ped"].sum())


@pytest.mark.unit
def test_design_matrix_appends_ride_extras_and_leaves_walk_columns_alone(
    walk_data: SegmentData,
) -> None:
    years = range(2019, 2022)
    walk_x = design_matrix(walk_data, years)
    ride = _with_bikes(walk_data)
    ride_as_walk = replace(ride, target_col="is_ped", extra=None)

    ride_x = design_matrix(ride, years)

    assert list(ride_x.columns) == [*walk_x.columns, *RIDE_EXTRA_COLUMNS]
    pd.testing.assert_frame_equal(design_matrix(ride_as_walk, years), walk_x)
    pd.testing.assert_frame_equal(ride_x[RIDE_EXTRA_COLUMNS], ride.extra, check_names=False)


@pytest.mark.unit
def test_fit_spatial_on_cyclist_target_uses_the_extras(walk_data: SegmentData) -> None:
    ride = _with_bikes(walk_data)

    fit = fit_spatial(ride, range(2019, 2023))
    exp = fit.expected(ride)

    assert set(RIDE_EXTRA_COLUMNS) <= set(fit.spf.columns)
    assert np.isfinite(exp["eb"]).all()
    assert (exp["eb"] > 0).all()
    history = window_counts(ride, range(2019, 2023), ped=True)
    assert exp["history"].sum() == pytest.approx(history.sum())


@pytest.mark.unit
def test_every_ride_feature_maps_to_a_ride_factor(walk_data: SegmentData) -> None:
    x = design_matrix(_with_bikes(walk_data), range(2019, 2022))

    missing = [c for c in x.columns if c not in RIDE_SPEC.feature_to_factor]

    assert missing == []
    assert set(RIDE_SPEC.feature_to_factor.values()) <= set(RIDE_SPEC.spatial)
    assert tuple(RIDE_SPEC.temporal) == tuple(FACTOR_GROUPS)


@pytest.mark.unit
def test_ride_labels_use_traffic_risk_language() -> None:
    labels = " ".join([*RIDE_SPEC.spatial.values(), *RIDE_SPEC.temporal.values()]).lower()

    assert "cyclist" in labels
    for banned in ("safe", "dangerous", "crime", "guarantee"):
        assert banned not in labels


@pytest.mark.unit
def test_decompose_with_ride_spec_returns_ride_factor_columns() -> None:
    rng = np.random.default_rng(0)
    cols = ["log_aadt", "bike_protected", "log_bike_activity"]
    contrib = pd.DataFrame(rng.normal(0, 0.3, (20, 3)), columns=cols)
    temporal = pd.DataFrame(rng.normal(0, 0.2, (5, 4)), columns=list(RIDE_SPEC.temporal))
    zeros = np.zeros(20)

    dec = decompose(contrib, -3.0, zeros, zeros, zeros, temporal, spec=RIDE_SPEC)
    walk = decompose(contrib[["log_aadt"]], -3.0, zeros, zeros, zeros, temporal)

    assert list(dec.spatial.columns) == list(RIDE_SPEC.spatial)
    assert list(walk.spatial.columns) == list(WALK_SPEC.spatial)
    expected = contrib.iloc[3].sum() - 3.0 + temporal.iloc[2].sum()
    got = dec.base + dec.spatial.iloc[3].sum() + dec.temporal.iloc[2].sum()
    assert got == pytest.approx(expected, abs=1e-9)


@pytest.mark.unit
def test_as_target_relabels_the_task_column_without_mutating_input() -> None:
    frame = pd.DataFrame({"is_ped": [True, False, False], "is_bike": [False, True, False]})

    out = as_target(frame, "is_bike")

    assert out["is_ped"].tolist() == [False, True, False]
    assert frame["is_ped"].tolist() == [True, False, False]
    assert as_target(frame, "is_ped") is not frame
    with pytest.raises(KeyError):
        as_target(frame, "is_scooter")
