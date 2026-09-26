# PathPro — Devpost write-up (draft)

**Tagline:** See traffic risk before you walk into it.

**Live:** https://pathpro.tech (Vultr, Atlanta) · offline demo: https://pathpro.tech/?demo=1 · code: https://github.com/ShaikNagurShareef/PathPro

**Tracks and prizes to select:**
- Oracle of the Deep
- Aramco "A Marina's Mission"
- Best Overall
- MLH Best Use of Tiger Data
- MLH Best Use of Vultr
- MLH Best Use of MongoDB Atlas
- MLH Best Use of ElevenLabs
- MLH Best .tech Domain
- MLH Best Use of Gemini API (if offered)
- Notability "Trust the Process"
- Create-X interest

## Inspiration

Walking from Klaus to Midtown MARTA at night, two routes look identical on a map, but they aren't. Atlanta's pedestrian deaths concentrate on a small share of streets, and that risk rises and falls with the hour and the weather. Navigation apps optimize time and say nothing about it. We wanted to make that invisible, time-dependent traffic risk visible, and offer a route that trades a few minutes for a lot less exposure.

A mentor tried our first version on his phone and told us it wasn't intuitive: GPS should be a must-have, and the app should learn your patterns the way his car learned his morning drive. We rebuilt the experience around that feedback. We also added a personal-safety layer, with safeguards against the neighborhood stigma that crime maps are known for.

## What it does

- **Two taps to a lower-risk route.** Open PathPro, tap "Where to?", and pick a place. GPS fills in "Your location". The route card reads like a map app's: **"23 min · 54% less traffic risk · +4 min vs fastest · arrive 10:52 PM"**, with a big **Start** button.
- **Walking navigation.** The map follows you and a banner warns **"High traffic risk ahead · 10th St NW in 120 m"**, spoken once per stretch with ElevenLabs. It detects arrival. Without GPS, "Preview walk" plays the same experience, so it works at the expo table and offline.
- **Learns your routine, on your phone only.** After a couple of walks it offers "Heading back to Klaus? · lower-risk route one tap away". Walk history never leaves the device, and one tap clears it.
- **Risk Tides:** hour-by-hour, dry/wet, weekday/weekend traffic risk on about 50,000 street segments across the City of Atlanta.
- **"Why?" on every street:** factor bars that add up exactly to the score, crash history, and when crashes happened by hour (Tiger Data). A grounded LLM explanation (Groq, with Gemini as fallback) can be read aloud.
- **Personal-safety layer:**
  - Street lighting, foot traffic, and help points: 100 Georgia Tech blue-light emergency phones, plus police, fire, hospitals, and MARTA.
  - An optional "Well-lit & busier (after dark)" route preference.
  - An informational layer of Atlanta Police reported crimes against persons, grouped by area and time of day.
- **Share my walk:** a live link a friend can follow. If you're 10 minutes past your arrival time, PathPro asks "Everything OK?" with Call 911 and Share location.
- **Community street reports** (sidewalk blocked, signal out, construction detour, …) show on the map and routes for 14 days. They never change a score.
- **City Pulse:** area traffic-risk scores for all 3,537 hexes of the city.
- Works on phone and desktop. No login. The demo works offline.

## How we built it

- **Data:** about 250k public crash records from 8 ArcGIS layers (ARC, City of Atlanta, Central Atlanta Progress, Georgia Tech, 2013–2026).
  - We merged duplicates across sources, dropped personal fields, and snapped crashes to OpenStreetMap road segments.
  - We found a source storing local time as UTC by checking it against its reported light condition; agreement went from 60% to 94% after the fix.
  - Features: StreetLight pedestrian activity, 2023 traffic volumes, speed limits, lanes, bus boardings, sidewalks, signals, and crossings. No demographic or income features.
- **ML:** an exposure-aware safety performance function (Poisson GLM + monotone LightGBM, spatial-block cross-validation), blended with each street's history by Empirical Bayes. A multi-task Poisson GLM learns how risk shifts by hour, day, light, and rain. Every score splits exactly into plain-language factors.
- **Evaluation:** trained on 2020–23 and tested on 2024.
  - The 10% of street length PathPro ranks highest held **74.3%** of 2024 pedestrian crashes (95% spatial-block CI 70.5–78.3%).
  - That compares with 49.8% for ranking by past crashes, 53.8% for the City's High Injury Network, and 11.9% for a random ranking. ROC-AUC is 0.89.
  - Our score also captures more on the City High Injury Network's own share of street length.
- **Personal safety, with fairness designed in:**
  - Crime is **never** used in routing or in the traffic model. A test multiplies crime counts by 1,000 and checks that routes don't change.
  - The layer covers crimes against persons only (homicide, robbery, aggravated assault, simple assault). It excludes residences, jails, and shelters, fetches no addresses or victim fields, and aggregates to H3 hexes by time of day.
  - Bands use an Empirical-Bayes rate per unit of foot traffic, so an area with no reports is never marked "higher". A fairness note always sits beside the layer.
  - Lighting is known for only about 4% of streets. We say so, and unknown stays unknown rather than "dark".
- **Sponsors and the job each one does:**
  - **Vultr:** the whole app runs on a Vultr VM in Atlanta, with Caddy (automatic HTTPS), a hardened systemd service, and a firewall. One command provisions and deploys it.
  - **.tech:** **pathpro.tech**, read as "path protect"; the .tech finishes the word.
  - **Tiger Data** (TimescaleDB + PostGIS): the crash hypertable and hourly continuous aggregate behind "when crashes happened here", plus geometry and the versioned risk grid.
  - **MongoDB Atlas:**
    - Community reports use a 2dsphere viewport query, a 14-day TTL, atomic upserts that turn repeat reports into confirmations, and an aggregation summary.
    - Share my walk uses a TTL of 6 hours after the last update, hashed owner tokens, and optimistic-concurrency position updates.
  - **ElevenLabs:** spoken explanations and navigation alerts.
  - **Groq** (gpt-oss-120b/20b) with **Gemini** as fallback: grounded explanations. A validator rejects any sentence with a number not in the evidence, and any crime framing.
- **App:** React + MapLibre + deck.gl, FastAPI, and scipy Dijkstra routing. Both route plans take about 150 ms at the median.
- **Engineering:** test-first throughout (RED and GREEN commits), with independent code, ML, and security review passes.
  - About 850 automated tests: 157 data, 247 API, 427 web, and 19 end-to-end, including an offline demo and a GPS navigation flow.
  - 90%+ coverage per package.
- **AI tools (disclosed):**
  - Built with Claude Code following the ECC workflow: plan, test first, implement, independent review, verify.
  - Scope, product decisions (including the safety layer and its safeguards), and review were ours.
  - Frameworks and datasets are credited in the README and in docs/safety_sources.md.

## Challenges we ran into

- **Missing roads in the walk graph.** Most Midtown roads are missing from OpenStreetMap's walk network because their sidewalks are mapped separately. A third of pedestrian crashes couldn't snap until we modeled risk on road centerlines and let sidewalks inherit it (snap rate 66% → 96%).
- **Compressed route scores.** Every Midtown street is top-quartile at night, so whole-route scores looked alike. We rebuilt routing around risk density and total exposure.
- **"Not intuitive."** Our first UI stacked four panels over the map on a phone. We rebuilt it: map-first, GPS by default, a Google-Maps-style route sheet, walking navigation, and a proper desktop layout.
- **Adding safety without stigma.** Terciles on raw crime counts marked 563 areas with no reports as "higher", because few people walk there. We switched to an exposure-normalized Empirical-Bayes posterior and kept crime out of routing entirely.
- **A drawing bug hiding in plain sight.** OSMnx stores most edge geometries in the opposite direction, so every other edge was drawn backwards. Routes looked zigzagged and navigation overstated distance by 1.6×. We fixed the orientation and added a regression test.
- **Honest statistics.** Our ML reviewer caught bootstrap intervals that were too narrow (we now resample spatial blocks) and a weak temporal baseline, which revealed that rain adds little. We report it.

## Accomplishments we're proud of

- The model beats the City of Atlanta's own High Injury Network on future crashes, with confidence intervals shown.
- Every number on screen traces to the model. The factor bars add up exactly, and the AI can't invent numbers.
- A mentor's "why would anybody use this" became a two-tap flow with GPS, navigation, and learned routines in one afternoon.
- The personal-safety layer is useful and honest about its limits, and it never routes around neighborhoods.
- It stays usable when the weather API, the LLM, a database, GPS, or the Wi-Fi fails.

## What we learned

- Most of the work is data plumbing and honest evaluation, not model choice.
- Exposure bias is real in both crash and crime data. Normalizing by foot traffic and saying so makes the claims stronger.
- Watching one real person use the app on a phone taught us more than any test.

## What's next for PathPro

- Cycling and wheelchair profiles
- Citywide lighting data through a partnership with the City or Georgia Power
- Push notifications and background location for navigation
- A Vision Zero planning dashboard for the city and campus
- New cities by swapping one coverage polygon

## Built with

Python · FastAPI · LightGBM · scikit-learn · statsmodels · OSMnx · GeoPandas · H3 · SciPy · React · TypeScript · Vite · MapLibre GL · deck.gl · Groq · Gemini API · ElevenLabs · Tiger Data (TimescaleDB, PostGIS) · MongoDB Atlas · Vultr · Caddy · Playwright · Claude Code
