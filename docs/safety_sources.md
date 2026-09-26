# Personal-safety layer: sources, methods, coverage

Bundle `pp-20260926-1723-a5f81ca` (built from `pp-20260926-0348-5540dda`; traffic-risk files unchanged).
Pipeline: `python -m pathpulse_data.safety.fetch` then `python -m pathpulse_data.safety.export [--link]`.
Raw pulls go to `data/raw/safety_*.parquet`, which is gitignored and can be fetched again.

## Rules this layer follows

- **Crime stays out of routing and the model.** Crime data never enters routing cost or the traffic-risk model. The router receives only per-edge lighting and foot-traffic codes (`EdgeSignals`). Tests check that scaling crime counts by 1000x leaves every route unchanged.
- **Crimes against persons only.** The layer keeps homicide, robbery, aggravated assault, and simple assault.
  - It drops all property, drug, vice, society, and "suspicious person" categories.
  - Robbery is filed as "Property" in NIBRS. It is kept because it is taken by force or threat against a person.
  - Sex offenses are not included. Small per-hex counts could expose victims.
- **Public places only.** Incidents at private dwellings, jails, and shelters are excluded: `RESIDENCE_HOME`, `APARTMENT`, `JAIL_PRISON_PENITENTIARY_CORRECTIONS_FACILITY`, `SHELTER_MISSION_HOMELESS`. People don't walk there, and counting them would mark where people live or where services are.
- **Hex counts only.** Crimes are aggregated to H3 res-9 hexes (the City Pulse grid). No points, addresses, report numbers, or victim fields are fetched or shipped. The fetch requests only `OccurredFromDate, NIBRS_Offense, LocationType` and the point geometry.
- **No demographic or income features** appear anywhere in this layer.
- **Copy:** "reported crimes against persons", "well-lit", "busier", "help points". Bands read "lower / typical / higher", never "unsafe" or "dangerous".

## Sources

| Signal | Source | License | Date range | Rows used |
| --- | --- | --- | --- | --- |
| Crimes against persons | APD open data, `OpenDataWebsite_Crime_view` FeatureServer/0 ([portal](https://opendata.atlantapd.org/)) | City of Atlanta open data (public record) | 2024-09-27 to 2026-09-26 (24 mo for banding); counts shipped for 2025-09-27 to 2026-09-26 | 15,096 in the 4 categories. 8,918 were at excluded locations. 6,174 kept for 24 months, 3,268 for 12 months, 3,167 inside city hexes |
| Emergency call boxes | Georgia Tech Police / I&O `Call_Box_Location_View_Layer` ([map](https://fm-gis2.ad.gatech.edu/emergency-phones.html)) | Public GT GIS layer | Current | 122 (all active and outdoor). 100 remain after 30 m dedupe |
| Police, fire, hospitals, MARTA rail | OpenStreetMap via Overpass (osmnx) | ODbL 1.0 | Pulled 2026-09-26 | 21 police, 35 fire, 9 hospitals, 24 MARTA stations (after dedupe; Amtrak excluded) |
| Street lamps | OSM `highway=street_lamp` (191) plus City of Atlanta `Downtown_Lights_all_WFL1` (2,332) | ODbL / City open data | Current | 2,523 lamps |
| Lighting tags | OSM `lit=*` on walk edges and road centerlines (already in the pipeline's OSM pull) | ODbL | 2026 | 1,476 walk edges and 520 road segments tagged |
| Foot traffic | City of Atlanta StreetLight pedestrian activity, 250 ft hex zones (already ingested) | City of Atlanta open data | 2021 | 5 zones, all-days volume per StreetLight period |

**Searched but not available:**
- No public citywide City of Atlanta or Georgia Power streetlight inventory exists. ArcGIS Online has only CID-level layers outside the city: Cumberland, Tucker, Powder Springs.
- "Places open now" (optional in the brief) was skipped. OSM `opening_hours` coverage is thin, and it isn't needed for v1.

**Timestamps:** APD `OccurredFromDate` is true UTC. After conversion to Atlanta time, the hour profile has its expected 5–6 AM trough. Read naively, the trough would fall at 10–11 AM.

## Day parts (Atlanta time)

night 22–5 · morning 6–11 · afternoon 12–17 · evening 18–21. `/safety/hexes?hour=` picks the day part that contains the hour.

## Methods

**Foot traffic (activity):**
- StreetLight daily volume per period is converted to a mean hourly rate per day part. The periods are 0–6, 6–10, 10–15, 15–19, and 19–24 h; each hour takes its period's volume divided by the period's length.
- A hex's activity is the mean over the StreetLight zones in that hex.
- The bands are terciles pooled over every hex and day part, so nights read "quiet" relative to the whole day:
  - quiet: below 2.56 per hour
  - moderate: 2.56 to 9.06 per hour
  - busy: 9.06 per hour or more
- Road segments use the pipeline's per-segment StreetLight join (weekday and weekend blended 5:2) with the same thresholds.

**Lighting:**
- Each walk edge is `lit`, `unlit`, or `unknown`, taken from the first of these that applies:
  1. its own OSM `lit` tag
  2. its road segment's tag
  3. a mapped lamp within 25 m, which counts as lit
- Missing lamps are **never** read as unlit. Only an explicit `lit=no` or `disused` tag makes an edge unlit.
- Hex `lit_share` is lit length divided by known length. It is `null` unless lighting is known for at least 50% of the walkable length.

**Crime band (exposure-normalized, Empirical Bayes):**
- For each hex and day part:
  - y = crimes in the last 24 months
  - E = the expected count if every pedestrian-hour in the city had the same rate. E is proportional to the hex's mean hourly activity × the hours in the day part.
  - Hexes without StreetLight data use the citywide median activity.
- The relative rate θ = y / E gets a Gamma(α, α/m) prior. α comes from the method of moments (Clayton & Kaldor 1987). The posterior is Gamma(y + α, E + α/m).
- Bands:
  - "higher" when P(θ > m) ≥ 0.9 and y > 0
  - "lower" when P(θ < m) ≥ 0.9
  - otherwise "typical"
- **Why this differs from the brief:** the brief asked for citywide terciles. About 81% of hexes have zero reports in a given day part, so terciles forced 563 zero-report hexes into "higher" only because little walking happens there. Posterior bands never mark a hex with no reports as "higher".
- Resulting bands:

| Day part | lower | typical | higher | Crimes (12 mo) |
| --- | --- | --- | --- | --- |
| Night | 701 | 2,614 | 222 | 1,139 |
| Morning | 439 | 2,960 | 138 | 417 |
| Afternoon | 642 | 2,662 | 233 | 890 |
| Evening | 465 | 2,890 | 182 | 721 |

**Help points:**
- Kinds are `blue_light`, `police`, `fire`, `hospital`, and `marta`.
- Points of the same kind within 30 m are merged.
- The layer ships per-hex counts, plus each road segment's distance to its nearest help point.

## Coverage (honest)

| Signal | Coverage |
| --- | --- |
| Lighting | Known for **4.4%** of walkable length in the city (4.3% lit, 0.06% unlit). Only **56 of 3,537 hexes** get a `lit_share`, mostly downtown and in tagged OSM areas; everywhere else it is `null`. The lit-and-busy preference therefore runs mostly on foot traffic. |
| Foot traffic | 3,498 of 3,537 hexes. 43,621 of 49,915 road segments. The data is from 2021. |
| Help points | 189 total. 104 hexes have at least one. The blue lights are all on the Georgia Tech campus. |
| Crime | All 3,537 city hexes. 101 of the 3,268 kept 12-month reports fall outside the city grid and are dropped. |

## Route preference `lit_and_busy`

- **Timing:** it applies after dark only (solar elevation below −0.833°, the same astral rule as the model). By day, routes are identical to the default.
- **Penalty:** after dark, each edge's cost is multiplied by 1 + 1.0·[known unlit] + 0.5·[known quiet for the departure's day part]. Unknown values are neutral.
- **Candidate routes:** the same λ ladder generates candidates.
- **Constraints:** routes must stay within the existing detour budget (≤ 1.25× the fastest time and ≤ 6 extra minutes), and may add at most 10% traffic exposure over the fastest route.
- **Choice:** the candidate with the least unlit or quiet length wins. It must cut that length by at least 15% against the route the default plan would show. Otherwise the default plan is returned unchanged.
- **Results (real bundle, 40 random night trips of 0.8–2.5 km):**
  - 40% of routes change
  - median 88% less quiet or unlit length
  - median 16% *less* traffic exposure than the fastest route
  - both plans computed in p50 154 ms, p95 283 ms

**Route safety summary (`RouteOut.safety`):**
- `lit_share` and `busy_share` are measured by length; `busy_share` counts moderate or busy foot traffic. Each is `null` when less than half the route's length is known.
- `help_points_within_100m` counts help points within 100 m of the polyline, sampled every 20 m.
- `crimes_persons_nearby` sums the day part's 12-month counts over the hexes the route passes through. It is display only.
