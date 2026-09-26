"""Safety-signal sources: what is pulled, and the fairness filters applied to it.

Crime data is informational only. It never enters the traffic-risk model or routing cost.
Only reported crimes against persons in public-facing places are kept; property, drug,
vice, and "suspicious person" categories are never read. No addresses, report numbers,
or victim fields are requested from the source.
"""

from __future__ import annotations

from dataclasses import dataclass

from pathpulse_data.config import COA, Layer

APD_CRIME_URL = (
    "https://services3.arcgis.com/Et5Qfajgiyosiw4d/arcgis/rest/services/"
    "OpenDataWebsite_Crime_view/FeatureServer/0"
)
APD_PORTAL_URL = "https://opendata.atlantapd.org/"
GT_CALLBOX_URL = (
    "https://services5.arcgis.com/7WaXTZEsI88qiQGw/arcgis/rest/services/"
    "Call_Box_Location_View_Layer/FeatureServer/0"
)
GT_CALLBOX_MAP_URL = "https://fm-gis2.ad.gatech.edu/emergency-phones.html"
STREETLIGHT_PORTAL_URL = f"{COA}"  # Citywide-Pedestrian-Activity--250ftHex-- layers
OSM_URL = "https://www.openstreetmap.org/copyright"

# NIBRS offense -> display category. Robbery is filed under "Property" in NIBRS but is taken
# by force or threat against a person, so it is kept (as asked for by the product decision).
CRIME_CATEGORIES: dict[str, str] = {
    "Murder & Nonnegligent Manslaughter": "Homicide",
    "Robbery": "Robbery",
    "Aggravated Assault": "Aggravated assault",
    "Simple Assault": "Simple assault",
}

# Private dwellings and custodial or shelter settings are not where people walk, and counting
# them would mark where people live (or where services are) rather than public streets.
EXCLUDED_LOCATIONS: frozenset[str] = frozenset(
    {
        "RESIDENCE_HOME",
        "APARTMENT",
        "JAIL_PRISON_PENITENTIARY_CORRECTIONS_FACILITY",
        "SHELTER_MISSION_HOMELESS",
    }
)

CRIME_FIELDS = "OccurredFromDate,NIBRS_Offense,LocationType"  # never addresses or victims
CALLBOX_FIELDS = "phone_name,phone_status,location_code"


def crime_where(start_iso: str) -> str:
    offenses = ",".join(f"'{o}'" for o in sorted(CRIME_CATEGORIES))
    return f"NIBRS_Offense IN ({offenses}) AND OccurredFromDate >= DATE '{start_iso}'"


def crime_layer(start_iso: str) -> Layer:
    return Layer(
        "safety_apd_crime", APD_CRIME_URL, where=crime_where(start_iso), out_fields=CRIME_FIELDS
    )


CALLBOX_LAYER = Layer("safety_gt_callboxes", GT_CALLBOX_URL, out_fields=CALLBOX_FIELDS)

# OpenStreetMap tags pulled for help points and street lamps.
OSM_TAGS: dict[str, list[str]] = {
    "amenity": ["police", "fire_station", "hospital"],
    "railway": ["station"],
    "highway": ["street_lamp"],
}


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    license: str


SOURCES: tuple[Source, ...] = (
    Source(
        "Atlanta Police Department open data (NIBRS crime incidents)",
        APD_PORTAL_URL,
        "City of Atlanta open data (public record)",
    ),
    Source("Georgia Tech Police emergency call boxes", GT_CALLBOX_MAP_URL, "Public GT GIS layer"),
    Source(
        "City of Atlanta StreetLight pedestrian activity (2021)",
        STREETLIGHT_PORTAL_URL,
        "City of Atlanta open data",
    ),
    Source(
        "OpenStreetMap (lighting tags, street lamps, police, fire, hospitals, MARTA)",
        OSM_URL,
        "ODbL 1.0",
    ),
    Source(
        "City of Atlanta downtown streetlight inventory",
        f"{COA}/Downtown_Lights_all_WFL1/FeatureServer/0",
        "City of Atlanta open data",
    ),
)
