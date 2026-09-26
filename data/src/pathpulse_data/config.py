"""Static configuration: coverage area, source layers, and pipeline thresholds.

Changing city or coverage should only require editing this file (PRD NFR-16).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

TZ = ZoneInfo("America/New_York")
CITY_NAME = "Atlanta, Georgia, USA"
CITY_LAT, CITY_LON = 33.7756, -84.3963  # Georgia Tech: coverage centroid for weather/astral

# Street-level coverage: Georgia Tech + Midtown + Downtown (PRD Q1).
CORE_BBOX: tuple[float, float, float, float] = (-84.415, 33.745, -84.370, 33.795)
# Citywide envelope for City Pulse pulls (clipped to the city polygon later).
CITY_BBOX: tuple[float, float, float, float] = (-84.56, 33.64, -84.28, 33.89)

ARC = "https://services1.arcgis.com/Ug5xGQbHsD8zuZzM/arcgis/rest/services"
COA = "https://services2.arcgis.com/zLeajbicrDRLQcny/arcgis/rest/services"
CAP = "https://services3.arcgis.com/FWC2S7IFSuSHD4PZ/arcgis/rest/services"
GTMAPS = "https://services2.arcgis.com/I9cUOJUZvdGAJncI/arcgis/rest/services"


@dataclass(frozen=True)
class Layer:
    """One ArcGIS FeatureServer layer to snapshot."""

    key: str
    url: str
    where: str = "1=1"
    bbox: tuple[float, float, float, float] | None = CITY_BBOX
    geometry: bool = True
    out_fields: str = "*"


LAYERS: tuple[Layer, ...] = (
    # --- crashes: year-only spatial counts ---
    Layer("arc_crashes_2020_2024", f"{ARC}/Crashes2020_2024/FeatureServer/0"),
    Layer("arc_crashes_2019_2023", f"{ARC}/Crashes2019to2023/FeatureServer/0", bbox=CORE_BBOX),
    # --- crashes: timed ---
    Layer("coa_all_2022", f"{ARC}/COA_2022AllCrashes/FeatureServer/0"),
    Layer("coa_pedbike_2022", f"{ARC}/2022_COA_Pedestrian_and_bicycle_crashes/FeatureServer/0"),
    Layer("marta_all_2023", f"{ARC}/MARTACountyCrashes_2023/FeatureServer/0"),
    Layer("cap_downtown_2017_2021", f"{CAP}/Downtown_Transportation/FeatureServer/9"),
    Layer("coa_midtown_2019_2023", f"{COA}/Fiveyear_Crashdata_Midtown_WFL1/FeatureServer/0"),
    Layer("coa_ka_since_2013", f"{COA}/KACrashesSince2013/FeatureServer/0"),
    Layer(
        "gt_pedcyc_2021_2025",
        f"{GTMAPS}/Atlanta_Collisions_Involving_Ped_or_Cyclist/FeatureServer/3",
    ),
    # --- exposure and road design ---
    Layer("coa_aadt_2023", f"{COA}/SummaryStats_Routes_AADT/FeatureServer/17"),
    Layer("coa_centerline", f"{COA}/Centerline_ATLDOT/FeatureServer/0"),
    Layer("coa_speedlimit", f"{COA}/Speedlimit_COA/FeatureServer/0"),
    # --- context ---
    Layer("arc_ped_risk_factors", f"{ARC}/Atlanta_Region_Safety_Risk_Factors/FeatureServer/1"),
    Layer("arc_ped_signals", f"{ARC}/PedestrianSignals/FeatureServer/1"),
    Layer("coa_sidewalks", f"{COA}/Sidewalks_Inventory/FeatureServer/2"),
    Layer("coa_marta_bus_stops", f"{COA}/MARTA_Bus_Stops_COA/FeatureServer/0"),
    Layer("coa_school_zones", f"{COA}/School_Zones_with_Schedules/FeatureServer/0"),
    Layer("coa_downtown_lights", f"{COA}/Downtown_Lights_all_WFL1/FeatureServer/0"),
    # --- baselines only (never model features) ---
    Layer("coa_hin_2025", f"{COA}/HIN_Tiers_2025/FeatureServer/0"),
    Layer("arc_hin_severity", f"{ARC}/ARC_High_Injury_Network_Severity/FeatureServer/0"),
)

STREETLIGHT_ZONES: tuple[str, ...] = (
    "ZA11_StreetLight_joined_poly_features-87371",
    "ZA21_StreetLight_joined_poly_features-77997",
    "ZA31_StreetLight_joined_poly_features-91207",
    "ZA41_StreetLight_joined_poly_features-90926",
    "ZA51_StreetLight_joined_poly_features-88846",
)


def streetlight_url(zone: str) -> str:
    return f"{COA}/Citywide-Pedestrian-Activity--250ftHex--{zone}/FeatureServer/0"


@dataclass(frozen=True)
class Thresholds:
    """Spatial and temporal thresholds used across the pipeline (PRD §5.4)."""

    node_snap_m: float = 15.0
    edge_snap_m: float = 30.0
    sidewalk_inherit_m: float = 25.0
    dedupe_m: float = 20.0
    dedupe_minutes: int = 30
    wet_precip_mm: float = 0.1
    min_segment_len_m: float = 30.0
    limited_data_obs: int = 3
    georgia_bounds: tuple[float, float, float, float] = field(default=(-85.61, 30.36, -80.84, 35.0))


THRESHOLDS = Thresholds()
