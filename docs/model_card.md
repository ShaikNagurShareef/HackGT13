# PathPulse model card

**Model:** pedestrian traffic-risk forecaster for Atlanta road segments and citywide H3 cells.
**Version:** see `/meta` → `model_version`. Crash data runs through 2026-09-19.
**Intended use:** compare walking routes and understand where and when pedestrian traffic crashes concentrate.
**Not intended for:**
- a guarantee about any individual walk
- judging personal safety or crime
- enforcement
- insurance
- property decisions

## What the score is

- **Definition:** the score is the percentile, on a citywide 0–100 scale, of expected pedestrian traffic crashes per 100 m of street for a given hour, day group, and weather.
- **Bands:** Lower 0–24, Moderate 25–49, Elevated 50–74, High 75–100. "High" always means the top quarter of the city's street-hours.
- **Framing:** the score describes **where and when crashes concentrate**. It is not a per-person probability. Busy streets score higher partly because more people walk there. This is exposure bias, and we disclose it rather than hide it.

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
- One source stored local wall-clock time as UTC. We detected this because only 60% of its crashes agreed with the reported light condition, and fixed it (94% after the fix).
- The same crash in several sources is merged by collision id, or when within 20 m and 30 min (4,754 merges).

**Snapping:**
- A crash within 15 m of an intersection is split across that intersection's road segments.
- Otherwise it goes to the nearest road within 30 m.
- 96% of pedestrian crashes snap. Most of the rest are on interstates, which are excluded by design.

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
- **No demographic, income, race, or crime features.** ARC's income, race, and environmental-justice flags were removed.
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
- 95% confidence intervals come from 400 bootstrap resamples of 47 H3 res-8 spatial blocks.

| 2024 holdout (225 pedestrian crashes) | Top 10% length | Top 5% length | At HIN's 20.3% | ROC-AUC | PR-AUC |
| --- | --- | --- | --- | --- | --- |
| PathPulse (Empirical Bayes ensemble) | **45.8%** [37.2, 55.6] | 28.9% | **69.2%** | **0.866** | **0.397** |
| Model only (no EB) | 45.8% | 28.9% | 70.7% | 0.867 | 0.397 |
| Past pedestrian crash density | 41.4% | 26.6% | 58.4% | 0.743 | 0.279 |
| City High Injury Network 2025 | 33.9% | 16.3% | 53.8% | 0.680 | 0.194 |
| ARC structural flags (demographic flags removed) | 29.2% | 14.2% | 50.7% | 0.776 | 0.198 |
| Random | 11.4% | 6.0% | 23.6% | 0.529 | 0.093 |

- **2023 check (train 2020–2022):** PathPulse 56.2% vs past-crash ranking 47.3% vs HIN 30.7%. ROC-AUC 0.868.
- **City Pulse:**
  - 2024: top 10% of cells held **74.5%** (past crashes 66.1%, random 13.1%). ROC-AUC 0.916.
  - 2023: 69.2% vs 58.8%.
- **Temporal model:** 12.5% lower Poisson deviance than a flat time profile on held-out 2022–2023 pedestrian crashes. Against a fair smoothed hour × day baseline, light and rain add **no measurable improvement** (−0.4%). Their effects are small in Atlanta's data: rain about ×1.04–1.08, darkness about ×1.3 relative to daytime at the same hour group. The Dry/Wet toggle is therefore subtle, and we say so.

### Honest caveats

- **2024 was looked at during development.** Neighborhood features were added after reviewing results, so treat the 2023 check as the cleaner second opinion.
- **Gain over past-crash ranking.** On 2024 it is +4.4 points, with a spatial-block CI of −0.1 to +9.6. It is consistent across both holdout years but not significant on 2024 alone.
- **The HIN comparison is conservative against us.** The HIN targets killed and serious crashes of all modes and was likely built with 2023–2024 data.
- **Counts are under-predicted.** 2024 recorded more pedestrian crashes (140 predicted vs 225 observed). Pedestrian share rose from 1.8% to 2.5% while total crashes stayed flat, which suggests a coding change. We claim **ranking**, not calibrated counts.
- **Post-period infrastructure.** Street features (OSM signals and crossings, 2023 AADT, current speed limits) are snapshots taken after or during the test period.

## Explanations and responsible AI

- **Attribution:** every displayed score is decomposed exactly. Factors are added from largest to smallest effect, and each gets the score change it causes, so the bars always sum to the score. This is property-tested on 200 random cases.
- **LLM input:** the LLM (Groq, then Gemini) receives only server-built JSON evidence, and no user text ever reaches the prompt.
- **LLM output validation.** Output is rejected, and a deterministic template shown instead, if it:
  - contains a number or time not in the evidence
  - uses "safe", "crime", "dangerous area", or similar framing
  - has more than three sentences
  - is truncated
- **Other safeguards:** no tracking or analytics. Guest locations are not stored.

## Known limitations

- **Exposure bias:** busy streets look riskier partly because more people walk there.
- **Under-reporting:** crash reports under-count minor pedestrian crashes.
- **Post-crash changes:** streets change after crashes (road diets, new signals).
- **Coverage:** street-level routing covers Georgia Tech, Midtown, and Downtown. City Pulse covers the City of Atlanta at area level.
- **Pedestrian activity data:** StreetLight activity is from 2021.
