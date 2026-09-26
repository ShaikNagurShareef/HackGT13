"""Write the artifact bundle consumed by the backend and frontend (no pandas needed there)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pathpulse_data.config import INTERIM_DIR, THRESHOLDS
from pathpulse_data.export.assemble import Assembled
from pathpulse_data.export.factors import SPATIAL_FACTORS, TEMPORAL_FACTORS
from pathpulse_data.network.inherit import inherit_segments
from pathpulse_data.network.layers import UTM

COORD_DECIMALS = 5
KIND_CODES = {"road": 0, "crossing": 1, "path": 2}
CONFIDENCE_HIGH, CONFIDENCE_MEDIUM = 15.0, THRESHOLDS.limited_data_obs


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, separators=(",", ":"), default=_json_default))


def _json_default(value: object) -> object:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value)}")


def _round_coords(geom: shapely.Geometry) -> list[list[float]]:
    return [[round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)] for x, y in geom.coords]


def segment_history(n_segments: int) -> pd.DataFrame:
    """Per-segment crash history summary (PRD EXP-03) and confidence (EXP-02)."""
    snaps = pd.read_parquet(INTERIM_DIR / "crash_segments.parquet")
    yearly = snaps.loc[snaps["stream"] == "yearly"]
    timed = snaps.loc[snaps["stream"] == "timed"].merge(
        pd.read_parquet(
            INTERIM_DIR / "crashes_timed.parquet",
            columns=["crash_id", "light_report", "surface_report"],
        ),
        on="crash_id",
    )
    idx = pd.RangeIndex(n_segments)
    total = yearly.groupby("seg_id")["weight"].sum().reindex(idx, fill_value=0.0)
    ped = (
        yearly.loc[yearly["is_ped"]].groupby("seg_id")["weight"].sum().reindex(idx, fill_value=0.0)
    )
    dark = timed["light_report"].astype(str).str.startswith("Dark") * timed["weight"]
    wet = timed["surface_report"].astype(str).str.contains("Wet|Water|Ice|Snow") * timed["weight"]
    t_total = timed.groupby("seg_id")["weight"].sum().reindex(idx)
    dark_share = (dark.groupby(timed["seg_id"]).sum().reindex(idx) / t_total).fillna(0.0)
    wet_share = (wet.groupby(timed["seg_id"]).sum().reindex(idx) / t_total).fillna(0.0)
    confidence = np.where(
        total >= CONFIDENCE_HIGH, "high", np.where(total >= CONFIDENCE_MEDIUM, "medium", "limited")
    )
    return pd.DataFrame(
        {
            "crashes": total.round(1),
            "ped_crashes": ped.round(1),
            "dark_share": dark_share.round(3),
            "wet_share": wet_share.round(3),
            "confidence": confidence,
        },
        index=idx,
    )


def write_segments(out: Path, asm: Assembled) -> pd.DataFrame:
    segs = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").sort_values("seg_id")
    history = segment_history(len(segs))
    names = segs["name"].astype("string").str.split(";").str[0].fillna("Unnamed street")
    meta = pd.DataFrame(
        {
            "name": names.to_numpy(),
            "road_group": segs["road_group"].to_numpy(),
            "length_m": segs["length"].round(1).to_numpy(),
            "eb": asm.expected["eb"].to_numpy(),
            "spf": asm.expected["spf"].to_numpy(),
        },
        index=pd.RangeIndex(len(segs)),
    ).join(history)
    features = [
        {
            "type": "Feature",
            "id": int(i),
            "geometry": {"type": "LineString", "coordinates": _round_coords(g)},
            "properties": {
                "n": meta.at[i, "name"],
                "g": meta.at[i, "road_group"][0],
                "c": meta.at[i, "confidence"][0],
            },
        }
        for i, g in enumerate(segs.geometry)
    ]
    _dump(out / "segments.geojson", {"type": "FeatureCollection", "features": features})
    _dump(out / "seg_meta.json", {col: meta[col].tolist() for col in meta.columns})
    return meta


def write_factors(out: Path, asm: Assembled) -> None:
    dec = asm.decomposition
    np.save(out / "spatial_factors.npy", dec.spatial.to_numpy(np.float32))
    rows = [
        {
            "day_group": dg,
            "hour": int(h),
            "light": light,
            "wet": bool(wet),
            "values": [round(float(v), 6) for v in vals],
        }
        for (dg, h, light, wet), vals in zip(
            dec.temporal.index, dec.temporal.to_numpy(), strict=True
        )
    ]
    _dump(
        out / "factors.json",
        {
            "base": dec.base,
            "spatial": [{"key": k, "label": v} for k, v in SPATIAL_FACTORS.items()],
            "temporal": [{"key": k, "label": v} for k, v in TEMPORAL_FACTORS.items()],
            "temporal_rows": rows,
            "quantiles": asm.quantiles.tolist(),
        },
    )


def write_frames(out: Path, asm: Assembled) -> None:
    for key, buf in asm.frames.items():
        (out / f"frames_{key}.bin").write_bytes(buf.tobytes())


def write_walk_graph(out: Path) -> dict[str, int]:
    """Routing graph (both directions) with the road segment each edge inherits risk from."""
    nodes = gpd.read_parquet(INTERIM_DIR / "walk_nodes.parquet")
    edges = gpd.read_parquet(INTERIM_DIR / "walk_edges.parquet")
    roads = gpd.read_parquet(INTERIM_DIR / "road_segments.parquet").to_crs(UTM)
    seg = inherit_segments(edges.to_crs(UTM), roads[["seg_id", "geometry"]]).to_numpy()
    index = {osmid: i for i, osmid in enumerate(nodes["osmid"])}
    coords = [_round_coords(g) for g in edges.geometry]
    offsets = np.cumsum([0] + [len(c) for c in coords])
    np.savez_compressed(
        out / "walk_graph.npz",
        node_lon=nodes.geometry.x.to_numpy(),
        node_lat=nodes.geometry.y.to_numpy(),
        edge_u=edges["u"].map(index).to_numpy(np.int32),
        edge_v=edges["v"].map(index).to_numpy(np.int32),
        edge_len=edges["length"].to_numpy(np.float32),
        edge_seg=seg.astype(np.int32),
        edge_kind=edges["kind"].map(KIND_CODES).to_numpy(np.uint8),
        coords=np.asarray([p for c in coords for p in c], dtype=np.float64),
        coord_offsets=offsets.astype(np.int32),
    )
    return {"nodes": len(nodes), "edges": len(edges), "edges_with_road": int((seg >= 0).sum())}


def write_hotspot_nodes(out: Path) -> int:
    nodes = gpd.read_parquet(INTERIM_DIR / "road_nodes.parquet")
    segs = pd.read_parquet(INTERIM_DIR / "road_segments.parquet", columns=["seg_id", "u", "v"])
    incident = pd.concat(
        [
            segs[["u", "seg_id"]].rename(columns={"u": "n"}),
            segs[["v", "seg_id"]].rename(columns={"v": "n"}),
        ]
    )
    by_node = incident.groupby("n")["seg_id"].apply(lambda s: sorted(set(s)))
    by_node = by_node[by_node.map(len) >= 3]
    pos = nodes.set_index("osmid").geometry
    rows = [
        [round(pos[n].x, COORD_DECIMALS), round(pos[n].y, COORD_DECIMALS), ids]
        for n, ids in by_node.items()
    ]
    _dump(out / "hotspot_nodes.json", rows)
    return len(rows)


def write_manifest(out: Path, manifest: dict[str, Any]) -> None:
    files = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    _dump(out / "manifest.json", {**manifest, "files": files})
