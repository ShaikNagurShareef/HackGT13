# PathPro model card

**Model:** pedestrian traffic-risk forecaster for Atlanta road segments and citywide H3 cells.
**Version:** see `/meta` → `model_version`. Crash data runs through 2026-09-19.
**Intended use:** compare walking routes and understand where and when pedestrian traffic crashes concentrate.
**Not intended for:**
- a guarantee about any individual walk
- judging whether a place or a person is safe (see the separate personal-safety layer below)
- enforcement
- insurance
- property decisions

## What the score is

- **Definition:** the score is the percentile, on a citywide 0–100 scale, of expected pedestrian traffic crashes per 100 m of street for a given hour, day group, and weather.
- **Bands:** Lower 0–24, Moderate 25–49, Elevated 50–74, High 75–100. "High" always means the top quarter of the city's street-hours.
- **Framing:** the score describes **where and when crashes concentrate**. It is not a per-person probability. Busy streets score higher partly because more people walk there. This is exposure bias, and this card discloses it rather than hiding it.

## Data

| Source | Years | Use |
| --- | --- | --- |
| ARC "Crashes 2020–2024" (year only) | 2020–2024 | Pedestrian crash labels, non-pedestrian crash density |
| City of Atlanta 2022 all crashes; 2022 pedestrian/bicycle crashes | 2022 | Timed crashes (hour, light, surface) |
| MARTA-county crashes 2023 | 2023 | Timed crashes with pedestrian flag |
| Central Atlanta Progress downtown crashes | 2017–2021 | Timed crashes |
| City Midtown five-year crashes; serious/fatal since 2013 | 2013–2023 | Timed crashes |
| Georgia Tech pedestrian/cyclist collisions | 2021–2025 | Timed crashes |
| StreetLight pedestrian activity (City of Atlanta) | 2021 | Pedestrian exposure feature |
| City 2023 AADT, speed limits, centerline lanes and ownership | 2023–2025 | Vehicle exposure and design |
| OpenStreetMap | 2026 | Road and walk networks, signals, crossings, destinations |
| Open-Meteo archive | 2013–2025 | Hourly precipitation for wet/dry exposure |

**Cleaning:**
- Records with missing, (0,0), or out-of-state coordinates are dropped and counted.
- Personal fields that some sources contain (names, ages, narratives) are never read into the pipeline output.
- One source stored local wall-clock time as UTC. I detected this because only 60% of its crashes agreed with the reported light condition, and fixed it (94% after the fix).
- The same crash in several sources is merged by collision id, or when within 20 m and 30 min (4,754 merges).

**Snapping:**
- A crash within 15 m of an intersection is split across that intersection's road segments.
- Otherwise it goes to the nearest road within 30 m.
- 95% of pedestrian crashes snap. Most of the rest are on interstates, which are excluded by design.

## Models

**Spatial model (per street segment):**
- **Features:**
  - traffic volume, speed limit, lanes, road class, ownership
  - intersection degree, signals, crossings
  - pedestrian activity
  - bus stops and boardings, rail distance
  - sidewalk condition, school zones
  - restaurants and nightlife
  - vehicle-crash density
  - pedestrian and vehicle crashes on nearby streets within 200 m, from the training years only
- **No demographic, income, race, or crime features.** ARC's income, race, and environmental-justice flags were removed. The personal-safety layer below is separate and never feeds this model.
- **Ensemble:** Poisson GLM + monotone LightGBM, combined in log space. Blend weight and boosting rounds are chosen by spatial-block cross-validation on H3 res-7 blocks.
- **Empirical Bayes:** blends the model with each segment's own pedestrian crash history. The weight k is chosen by predicting the last training year from the earlier ones.

**Temporal model:**
- **Form:** Poisson GLM on (road group × day group × hour × light × wet × pedestrian?) cells, with log(exposure hours) as an offset and year effects.
- **Shared effects:** all-mode crashes teach the shared hour shape.
- **Pedestrian terms:** pedestrian-specific terms learn how pedestrians differ from the all-mode shape.
- **Light and rain definitions:** identical for crashes and exposure hours, from solar elevation and Open-Meteo precipitation ≥ 0.1 mm.

**City Pulse:** the same approach on 3,537 H3 res-9 cells. It uses citywide road-network, AADT, speed, StreetLight, and transit features, and a road-group mixture of the temporal model.

## Evaluation

**Protocol:**
- Train on 2020–2023, test on 2024 pedestrian crashes. A second check trains on 2020–2022 and tests on 2023.
- The headline metric is the share of held-out pedestrian crashes on the top X% of **street length** ranked by predicted risk. Ranking by length stops a model from looking good by picking long segments.
- 95% confidence intervals come from 400 bootstrap resamples of 614 H3 res-8 spatial blocks.

| 2024 holdout (543 pedestrian crashes, whole city) | Top 10% length | Top 5% length | At HIN's 9.8% | ROC-AUC | PR-AUC |
| --- | --- | --- | --- | --- | --- |
| PathPro (Empirical Bayes ensemble) | **74.3%** [70.5, 78.3] | **61.1%** | **73.9%** | **0.889** | **0.277** |
| Model only (no EB) | 74.3% | 61.2% | 73.8% | 0.889 | 0.276 |
| Past pedestrian crash density | 49.8% | 44.4% | 49.8% | 0.716 | 0.160 |
| City High Injury Network 2025 | 53.8% | 39.3% | 53.7% | 0.694 | 0.088 |
| ARC structural flags (demographic flags removed) | 51.2% | 26.2% | 50.1% | 0.792 | 0.085 |
| Random | 11.9% | 6.1% | 11.6% | 0.494 | 0.027 |

- **Confidence intervals** resample 614 H3 res-8 spatial blocks across the city.
- **Gain over past-crash ranking:** +24.5 points on 2024 (95% CI +20.4 to +28.8).
- **2023 check (train 2020–2022):** PathPro 68.1% vs HIN 54.2% vs past-crash ranking 45.5%. ROC-AUC 0.869.
- **City Pulse:**
  - 2024: top 10% of cells held **74.5%** (past crashes 66.1%, random 13.1%). ROC-AUC 0.916.
  - 2023: 69.2% vs 58.8%.
- **Temporal model:** 24.5% lower Poisson deviance than a flat time profile on held-out 2022–2023 pedestrian crashes (889 crashes). Against a smoothed hour × day baseline, light and rain add a small gain (+1.3%). Effects: darkness ×1.6, wet pavement ×1.12, with pedestrians more affected by darkness than all crashes (×1.11).

### Honest caveats

- **Citywide ranking is easier than ranking a dense core.** Citywide includes many quiet residential streets. Within Downtown/Midtown alone (the earlier core-only model), the top 10% of length held 45.8% of 2024 crashes vs 41.4% for past-crash ranking.
- **2024 was looked at during development.** Treat the 2023 check as the cleaner second opinion.
- **The HIN comparison is conservative against PathPro.** The HIN targets killed and serious crashes of all modes and was likely built with 2023–2024 data.
- **Counts are under-predicted** (411 predicted vs 543 observed in 2024). Pedestrian share rose while total crashes stayed flat, which suggests a coding change. PathPro claims **ranking**, not calibrated counts.
- **Post-period infrastructure.** Street features (OSM signals and crossings, 2023 AADT, current speed limits) are snapshots taken after or during the test period.

## Explanations and responsible AI

- **Attribution:** every displayed score is decomposed exactly. Factors are added from largest to smallest effect, and each gets the score change it causes, so the bars always sum to the score. This is property-tested on 200 random cases.
- **LLM input:** the LLM (Grok, then Groq, then Gemini) receives only server-built JSON evidence, and no user text ever reaches the prompt.
- **LLM output validation.** Output is rejected, and a deterministic template shown instead, if it:
  - contains a number or time not in the evidence
  - uses "safe", "crime", "dangerous area", or similar framing
  - has more than three sentences
  - is truncated
- **Other safeguards:** no tracking or analytics. Guest locations are not stored.
- **Community street reports (MongoDB Atlas) do not feed the model.** They are shown beside scores for context only and never change a score, a route choice, or the LLM's evidence.

## Known limitations

- **Exposure bias:** busy streets look riskier partly because more people walk there.
- **Under-reporting:** crash reports under-count minor pedestrian crashes.
- **Post-crash changes:** streets change after crashes (road diets, new signals).
- **Coverage:** street-level scores and routing cover the whole City of Atlanta (49,915 road segments). City Pulse adds area-level scores for the same area.
- **Pedestrian activity data:** StreetLight activity is from 2021.

## Personal-safety layer (separate from this model)

Added 2026-09-26. It sits beside the traffic-risk model and never changes its scores. Sources and coverage: [safety_sources.md](safety_sources.md).

- **Signals:** street lighting (OSM `lit` tags, OSM street lamps, the City's downtown lights layer; known for only ~4.4% of walkable length, so unknown lighting stays unknown and is never treated as unlit), foot traffic (StreetLight activity by day part), and help points (Georgia Tech emergency call boxes, police, fire, hospitals, MARTA).
- **Optional route preference:** "Well-lit & busier (after dark)". Only after sunset: known-unlit edges cost ×2 and known-quiet edges ×1.5. The traffic-exposure increase over the fastest route is capped at 10%, and the default plan is kept unless unlit-or-quiet length drops by at least 15%. The default preference stays "lower traffic risk".
- **Reported crimes against persons (informational only):** Atlanta Police open data (homicide, robbery, aggravated assault, simple assault), excluding residences, jails, and shelters. Only date, offense, and location type are fetched. Reports are aggregated to H3 res-9 hexes by day part.
  - Bands come from an Empirical-Bayes posterior of reports per unit of pedestrian activity. "Higher" needs at least 90% posterior probability above the citywide rate and at least one report, so a hex with no reports is never "higher".
  - Never used in routing cost, the traffic model, or LLM explanations. A test scales crime counts by 1,000 and asserts routes are unchanged.
  - Always shown with a fairness note: reports reflect where police record incidents, not how people should feel about a neighborhood.
- **Limits:** police reports undercount some incidents and overcount heavily patrolled areas. The foot-traffic data is from 2021. Lighting coverage is sparse.

## Ride model (bike, e-bike, scooter)

Added 2026-09-26. It ranks streets by traffic risk to people on bikes and scooters, and runs on OpenStreetMap's bike network. The walk model and its files are unchanged.

- **Network and features:**
  - OSMnx `network_type="bike"` over the City of Atlanta: 49,824 nodes and 65,997 edges.
  - Road features (speed, lanes, AADT, class) are conflated as for walking.
  - Bike infrastructure comes from the City's `Bike_Facilities_Public_View` (existing facilities: protected, painted, shared) and OSM cycleway tags, plus Atlanta BeltLine adjacency (ABI layer and OSM).
- **Labels:** cyclist-involved crashes (ARC `Bicycle_Related` flag, 2020–2024: 29, 95, 123, 132, 175 by year). 551 of 554 snapped to a road segment. Rider ages are dropped.
- **Exposure is a proxy.** The City publishes no StreetLight bicycle layer. The model uses ARC's Strava 2024 ride and e-bike origins and destinations per H3 res-8 hex, plus facility presence and pedestrian activity. Dropping Strava gives 69.5% [63.9, 75.8] on 2024, so it does not drive the result.
- **Training label: pooled pedestrian + cyclist crashes, always scored on cyclist crashes only.** It was chosen on the 2023 validation year: 69.0% pooled vs 59.7% cyclist-only.
  - The cyclist-only candidate scored 57.4% [48.1, 65.6] on 2024 and lost to simply reusing the walk model.
  - I looked at 2024 during development, so 2023 is the cleaner check.
- **2024 holdout (174 cyclist crashes), top 10% of street length:**

  | Method | Capture |
  | --- | --- |
  | Ride model | **69.9% [64.0, 76.1]** |
  | Walk model reused | 66.4% (gain +1.3 to +6.2 points) |
  | City High Injury Network | 43.6% |
  | Past cyclist crashes only | 30.4% (gain +30.9 to +46.3 points) |
  | Random | 12.0% |

  ROC-AUC is 0.866. On the 2023 validation year the model captures 69.0%, against 22.1% for past crashes.
- **Temporal model:** a cyclist Poisson GLM on 48 cyclist crashes plus the all-mode hourly shape. It beats the walk structure on held-out 2022–23 crashes (deviance 0.516 vs 0.580). Light and rain add little; the wet effect is ×0.86 because exposure is counted in clock hours, not riders. The shipped model is a 2017–2023 refit of the evaluated 2017–2021 model.
- **Limits:**
  - Pooled training means the counts are **not calibrated for cyclists**; PathPro claims ranking only.
  - E-bike and scooter reuse this model with different speeds (22 and 18 km/h). Scooter crashes are identified only in the K/A layer (75 serious or fatal) and are not counted as cyclists.
  - Today's bike facilities are applied to past years.
