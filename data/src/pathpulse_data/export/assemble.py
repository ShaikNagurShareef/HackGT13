"""Assemble final model outputs: decomposition, frames, per-segment metadata."""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from datetime import date, datetime, time

import numpy as np
import pandas as pd

from pathpulse_data.config import TZ
from pathpulse_data.export.factors import WALK_SPEC, Decomposition, FactorSpec, decompose
from pathpulse_data.export.frames import build_quantiles, pack_frames, score_from_log_density
from pathpulse_data.model.dataset import SegmentData, design_matrix, effective_length
from pathpulse_data.model.spatial import SpatialFit
from pathpulse_data.model.temporal import CELL_KEYS, LEVELS, TemporalModel
from pathpulse_data.timeseries.exposure import light_at

log = logging.getLogger(__name__)
CONDITIONS = {"dry": False, "wet": True}
DAY_GROUPS = LEVELS["day_group"]


@dataclass(frozen=True)
class Assembled:
    decomposition: Decomposition
    quantiles: np.ndarray
    frames: dict[str, np.ndarray]  # "{day_group}_{cond}" -> hour-major uint8
    reference_dates: dict[str, str]
    frame_light: dict[str, list[str]]  # day_group -> light label per hour
    expected: pd.DataFrame  # spf, eb, history per segment (annual)
    temporal_effects: dict[str, float]


def reference_dates(today: date) -> dict[str, date]:
    """Next date of each day group on/after `today` (light depends on the season)."""
    out: dict[str, date] = {}
    for offset in range(8):
        d = date.fromordinal(today.toordinal() + offset)
        wd = d.weekday()
        group = {4: "friday", 5: "saturday", 6: "sunday"}.get(wd, "weekday")
        out.setdefault(group, d)
    return out


def temporal_table(model: TemporalModel, reference: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Factor contributions for every (day_group, hour, light, wet) + per-road-group base."""
    grid = pd.DataFrame(
        itertools.product(
            LEVELS["road_group"], DAY_GROUPS, range(24), LEVELS["light"], (False, True)
        ),
        columns=list(CELL_KEYS),
    )
    contrib = model.log_contributions(grid, reference=reference)
    road_base = contrib.groupby(grid["road_group"])["_base"].mean()
    spread = float(contrib.groupby(grid["road_group"])["_base"].std().max())
    assert spread < 1e-8, "temporal base must be constant within a road group"
    local = grid["road_group"] == "local"
    table = contrib.loc[local].drop(columns="_base")
    table.index = pd.MultiIndex.from_frame(grid.loc[local, ["day_group", "hour", "light", "wet"]])
    return table, road_base


def assemble(
    fit: SpatialFit,
    tmodel: TemporalModel,
    t_reference: pd.DataFrame,
    data: SegmentData,
    today: date,
    spec: FactorSpec = WALK_SPEC,
) -> Assembled:
    expected = fit.expected(data)
    x = design_matrix(data, fit.train_years)
    contrib, spf_base = fit.spf.contributions(x)
    eb_adj = np.log(expected["eb"].to_numpy() / expected["spf"].to_numpy())
    log_len = np.log(effective_length(data.features).to_numpy() / 100.0)
    table, road_base = temporal_table(tmodel, t_reference)
    seg_road_base = data.features["road_group"].map(road_base).to_numpy()
    dec = decompose(contrib, spf_base, eb_adj, log_len, seg_road_base, table, spec=spec)
    spatial_sum = dec.base + dec.spatial.sum(axis=1).to_numpy()

    refs = reference_dates(today)
    per_frame: dict[str, np.ndarray] = {}
    frame_light: dict[str, list[str]] = {}
    for group, cond in itertools.product(DAY_GROUPS, CONDITIONS):
        lights = [light_at(datetime.combine(refs[group], time(h, 30), TZ)).value for h in range(24)]
        frame_light[group] = lights
        rows = [dec.temporal.loc[(group, h, lights[h], CONDITIONS[cond])].sum() for h in range(24)]
        per_frame[f"{group}_{cond}"] = spatial_sum[None, :] + np.asarray(rows)[:, None]

    _check_identity(per_frame, expected, tmodel, t_reference, data, frame_light, log_len)
    quantiles = build_quantiles(np.concatenate([v.ravel() for v in per_frame.values()]))
    frames = {k: pack_frames(score_from_log_density(v, quantiles)) for k, v in per_frame.items()}
    return Assembled(
        decomposition=dec,
        quantiles=quantiles,
        frames=frames,
        reference_dates={k: v.isoformat() for k, v in refs.items()},
        frame_light=frame_light,
        expected=expected,
        temporal_effects=tmodel.pedestrian_effects(),
    )


def _check_identity(
    per_frame: dict[str, np.ndarray],
    expected: pd.DataFrame,
    tmodel: TemporalModel,
    reference: pd.DataFrame,
    data: SegmentData,
    frame_light: dict[str, list[str]],
    log_len: np.ndarray,
) -> None:
    """Decomposed log density must equal log(EB x multiplier / length) exactly."""
    group, hour, cond = "friday", 22, "wet"
    cells = pd.DataFrame(
        {
            "road_group": data.features["road_group"].to_numpy(),
            "day_group": group,
            "hour": hour,
            "light": frame_light[group][hour],
            "wet": CONDITIONS[cond],
        }
    )
    mult = tmodel.normalized_multiplier(cells, reference=reference).to_numpy()
    direct = np.log(expected["eb"].to_numpy()) + np.log(mult) - log_len
    got = per_frame[f"{group}_{cond}"][hour]
    err = float(np.max(np.abs(direct - got)))
    log.info("decomposition identity max error %.2e", err)
    assert err < 1e-6, f"decomposition identity violated: {err}"
