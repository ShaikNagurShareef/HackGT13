# PathPulse — Devpost write-up (draft)

**Tagline:** See traffic risk before you walk into it.

**Tracks and prizes to select:**
- Oracle of the Deep
- Aramco "A Marina's Mission"
- Best Overall
- MLH Best Use of Tiger Data
- MLH Best Use of Vultr
- MLH Best Use of ElevenLabs
- MLH Best .tech Domain
- MLH Best Use of Gemini API (if offered)
- Notability "Trust the Process"
- Create-X interest

## Inspiration

Walking from Klaus to Midtown MARTA at night, two routes look identical on a map, but they aren't. Atlanta's pedestrian deaths concentrate on a small share of streets, and that risk rises and falls with the hour. Navigation apps optimize time and say nothing about this. We wanted to make invisible, time-dependent traffic risk visible, and offer a route that trades a few minutes for a lot less exposure. We did it without crime data or demographics, which stigmatize neighborhoods.

## What it does

- **Risk Tides:** an hour-by-hour, dry/wet, weekday/weekend map of pedestrian traffic risk on about 50,000 street segments across the whole City of Atlanta.
- **Fastest vs PathPulse route.** Klaus → Midtown MARTA, Friday 10:30 PM in rain: **+4.2 min, 54% less traffic-risk exposure**, avoiding Peachtree Place and Williams St. When the fastest route is already the lower-risk one, PathPulse says so.
- **"Why is this street risky?"** A score dial, confidence badge, factor bars that sum exactly to the score, crash history, and when crashes happened by hour (Tiger Data).
- **City Pulse:** area-level traffic-risk scores for all 3,537 hexes of the City of Atlanta.
- **Grounded AI explanations** and **voice alerts**. No logins, and the demo works offline.

## How we built it

- **Data:** about 250k public crash records from 8 ArcGIS layers (ARC, City of Atlanta, Central Atlanta Progress, Georgia Tech, 2013–2026).
  - We merged the same crash across sources and dropped personal fields.
  - We caught a source that stored local time as UTC by checking it against the reported daylight/dark field (60% → 94% agreement after the fix).
  - Crashes were snapped to OpenStreetMap road segments.
  - Features: StreetLight pedestrian activity, 2023 traffic volumes, speed limits, lanes, bus boardings, sidewalks, signals, crossings.
- **ML:** an exposure-aware safety performance function (Poisson GLM + monotone LightGBM, spatial-block cross-validation), blended with each street's history by Empirical Bayes. A multi-task Poisson GLM learns how risk shifts by hour, day, light, and rain. Every score splits exactly into plain-language factors.
- **Evaluation:** trained on 2020–23 and tested on 2024.
  - The 10% of street length PathPulse ranks highest held **74.3%** of 2024 pedestrian crashes (95% spatial-block CI 70–78%).
  - That compares with 49.8% for past-crash ranking, 53.8% for the City High Injury Network, and 11.9% at random. It repeats on 2023 (68.1% vs 45.5%).
  - City Pulse: **74.5%** of crashes in the top 10% of areas. ROC-AUC 0.89 streets / 0.92 areas.
- **Sponsors and their jobs:**
  - **Groq** (gpt-oss-120b/20b) writes grounded explanations in under a second, with **Gemini** as fallback. A validator rejects any sentence with a number not in the evidence.
  - **ElevenLabs** speaks explanations and walk alerts.
  - **Tiger Data** (TimescaleDB + PostGIS) holds the crash hypertable, hourly continuous aggregates, geometry, and versioned risk grid.
  - **Vultr** hosts the FastAPI backend and site behind Caddy.
  - The **.tech** domain: pathpulse.tech.
- **App:** React + MapLibre + deck.gl, with FastAPI and scipy Dijkstra for routing (p95 about 120 ms).
- **Engineering:** test-first throughout. 252 automated tests (98 data, 72 API, 71 web, 11 end-to-end), 85–95% coverage per package, and Playwright end-to-end tests including an offline demo.
- **AI tools (disclosed):**
  - Built with Claude Code following the ECC workflow: plan, test first, implement, independent ML/security review, verify.
  - Scope, product decisions, and review were ours.
  - Frameworks and datasets are credited in the README.

## Challenges we ran into

- **Missing roads in the walk graph.** Most Midtown roads are missing from OpenStreetMap's walk network because their sidewalks are mapped separately. A third of pedestrian crashes couldn't snap until we modeled risk on road centerlines and let sidewalks inherit it (snap rate 66% → 96%).
- **Compressed route scores.** Every Midtown street is top-quartile at night, so whole-route scores looked alike. We re-built routing around risk density and total exposure instead.
- **Honest statistics.**
  - Our ML reviewer caught that segment-level bootstrap intervals were too narrow, so we resample spatial blocks.
  - It also caught that our temporal baseline was too weak, which revealed that rain adds little. We report it.

## Accomplishments we're proud of

- The model beats the City of Atlanta's own High Injury Network on future crashes, and we show the confidence intervals.
- Every number on screen traces to the model: the factor bars sum exactly, and the AI can't invent numbers.
- A full product that stays usable when the weather API, the LLM, the database, or the Wi-Fi fails.

## What we learned

- Most of the work is data plumbing and honest evaluation, not model choice.
- Exposure bias and label shifts are real. Saying so makes the claims stronger, not weaker.

## What's next for PathPulse

- Cycling and wheelchair profiles
- Exposure-normalized per-trip risk
- A Vision Zero planning dashboard for the city and campus
- Near-miss reports
- New cities by swapping one coverage polygon

## Built with

Python · FastAPI · LightGBM · scikit-learn · statsmodels · OSMnx · GeoPandas · H3 · SciPy · React · TypeScript · Vite · MapLibre GL · deck.gl · Groq · Gemini API · ElevenLabs · Tiger Data (TimescaleDB, PostGIS) · Vultr · Caddy · Playwright · Claude Code
