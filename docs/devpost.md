# PathPro — Devpost write-up (draft)

**Tagline:** See the risks on your way, before you go.

**Built by:** Nagur Shareef Shaik, solo, under the team name **Coding Claws** (Georgia State University), at HackGT 13.

**Live:** https://pathpro.tech (Vultr, Atlanta) · offline demo: https://pathpro.tech/?demo=1 · code: https://github.com/ShaikNagurShareef/PathPro · video: <YouTube link>

**Tracks and prizes (as entered on the Devpost form):**
- General track: Oracle of the Deep
- Sponsor track 1: Aramco "A Marina's Mission"
- Sponsor track 2: SpaceXAI "Make it Legendary"
- MLH: Best Use of ElevenLabs, Gemini API, TigerData, Vultr, MongoDB Atlas
- MLH: Best Use of Backboard (tick only after Ask PathPro is deployed and answering on pathpro.tech)
- MLH Best .tech Domain, through the domain question (pathpro.tech)
- Create-X interest

**Live status:** the Grok features, the Gemini image check, and Ask PathPro (Backboard) are built and tested, and Grok, Gemini, and Backboard were verified against the real APIs locally. They are not yet deployed to pathpro.tech. Sections and lines about them are gated below.

## Inspiration

I walk between Klaus, Tech Square, and Midtown MARTA late at night. My friends, especially women, already plan routes around well-lit, busier streets and text each other when they get home. Yet every navigation app I open answers only one question: what's fastest?

Atlanta's pedestrian deaths concentrate on a small share of streets, and that risk rises and falls with the hour and the weather. I wanted a map that shows where and when traffic risk is highest, a route that trades a few minutes for much less exposure, and better tools for anyone walking or riding alone at night.

A mentor tried my first version on his phone and told me it wasn't intuitive: GPS should be a must-have, and the app should learn your patterns the way his car learned his morning drive. I rebuilt the experience around that feedback. I added bikes, e-bikes, and scooters, because walking across a city isn't realistic. I also added a personal-safety layer, with safeguards against the neighborhood stigma that crime maps are known for.

## Who it's for

- **Anyone walking alone at night**, including women and girls who already plan around lighting and foot traffic:
  - a "Well-lit & busier (after dark)" route preference
  - help points on the map, including 100 Georgia Tech blue-light phones
  - **Share my walk**, so a friend can follow along live
  - a late check-in ("Everything OK?", with Call 911 and Share location)
- **Students and people without a car:** a MARTA hand-off for long walks, and Bike, E-bike, and Scooter modes.
- **Older adults and anyone who wants their eyes up, not on a screen:** spoken "high traffic risk ahead" alerts, large touch targets, and keyboard and screen-reader support.
- **Cities and campuses:** a ranked list of where fixes reach the most future crashes, and a picture of what a fixed street could look like.

## What it does

- **Two taps to a lower-risk route.** Open PathPro, tap "Where to?", and pick a place. GPS fills in "Your location". The route card reads like a map app's: **"23 min · 54% less traffic risk · +4 min vs fastest · arrive 10:52 PM"**, with a big **Start** button.
- **Walking navigation.** The map follows you and a banner warns **"High traffic risk ahead · 10th St NW in 120 m"**, spoken once per stretch. It detects arrival. Without GPS, "Preview walk" plays the same experience, so it works at the expo table and offline.
- **Learns your routine, on your phone only.** After a couple of walks it offers "Heading back to Klaus? · lower-risk route one tap away". Walk history never leaves the device, and one tap clears it.
- **Walk · Bike · E-bike · Scooter.** Walking 45 minutes across Atlanta isn't realistic, so PathPro also routes bikes, e-bikes, and scooters on OpenStreetMap's bike network with its own cyclist-risk model: Georgia Tech → Inman Park at 9 PM is **"28 min ride · 72% less traffic risk"** for +4 min. Long walks get a **MARTA hand-off** ("walk 8 min to North Ave station…") and a "Try Bike" shortcut. I deliberately don't route cars: risk-aware driving routes push traffic onto the neighborhood streets where people walk.
- **Risk Tides:** hour-by-hour, dry/wet, weekday/weekend traffic risk on about 50,000 street segments across the City of Atlanta.
- **"Why?" on every street:** factor bars that add up exactly to the score, crash history, and when crashes happened by hour (Tiger Data). A grounded LLM explanation (Grok first, then Groq, then Gemini, then a template) can be read aloud.
- **Personal-safety layer:**
  - Street lighting, foot traffic, and help points: 100 Georgia Tech blue-light emergency phones, plus police, fire, hospitals, and MARTA.
  - An optional "Well-lit & busier (after dark)" route preference.
  - An informational layer of Atlanta Police reported crimes against persons, grouped by area and time of day.
- **Share my walk:** a live link a friend can follow. If you're 10 minutes past your arrival time, PathPro asks "Everything OK?" with Call 911 and Share location.
- **Community street reports** (sidewalk blocked, signal out, construction detour, …) show on the map and routes for 14 days. They never change a score.
- **City Pulse:** area traffic-risk scores for all 3,537 hexes of the city.
- <!-- gated: publish after deploy --> **"Imagine this street redesigned"** (Grok Imagine, checked by Gemini) for planners, and **Ask PathPro** (Backboard) for anyone who wants to know how a score or a route was made. Details below.
- Works on phone and desktop. No login. The demo works offline.

<!-- Publish this section only after Grok is verified live on pathpro.tech (explanation source "grok", Grok Voice audio, one Imagine image with the Gemini check line). Publish the Ask PathPro bullet only after Ask answers on pathpro.tech. -->
## Make it Legendary: mission control for every walk home

I built PathPro the way a launch team works: start from first principles, test the way you fly, plan for engine-out, and reuse everything. Grok is part of the flight computer.

- **First principles, not vibes.** I didn't start from which streets *feel* risky. I started from about 250,000 real crash outcomes and pedestrian exposure, and let the data rank the streets. On a year the model never saw, the top 10% of street length held 74.3% of pedestrian crashes, against 53.8% for the City's own High Injury Network.
- **A launch window for your walk.** Risk Tides works like a weather-and-window board: traffic risk hour by hour, dry or wet, weekday or weekend. The route card is a go/no-go with the trade stated plainly: **+4 min buys 54% less traffic-risk exposure**.
- **Mission callouts with Grok Voice.** During navigation, PathPro calls out "High traffic risk ahead · 10th St NW in 120 m" in an expressive Grok Voice, so walkers keep their eyes on the street, not the screen.
- **Grok on the flight computer.** Grok writes the "Why?" explanation for each street, grounded in that street's own evidence. It can't add a number: a validator rejects any sentence with a figure that isn't in the evidence, and the risk score always comes from the model, never from the LLM.
- **Simulate before you build, with Grok Imagine.** On any street, a city or campus planner taps **"Imagine this street redesigned"**. PathPro builds the prompt on the server from that street's real factors: lanes, speed limit, crossings, lighting, and its top risk drivers. It never includes user text or street names. Grok Imagine then renders the evidence-based fixes: high-visibility crosswalks, curb extensions, a refuge island, a protected bike lane, street lighting, or a road diet. Every image is labeled "AI illustration of evidence-based street fixes by Grok Imagine — not a real photo". It's a way to see a Vision Zero fix before spending a dollar on concrete.
- **Grok draws, Gemini checks.** Before any illustration reaches the screen, Gemini looks at it next to the server's list of planned fixes. The card then says "Checked by Gemini: shows 3 of 4 planned fixes". An image with readable text, logos, or identifiable faces is never shown or cached: Grok gets one more try, and if that one is flagged too, the planner sees a friendly retry message. Gemini's answer is parsed strictly, so it can only confirm fixes that were actually planned. If Gemini can't be reached, the picture is shown without the check line instead of being blocked.
- **Ask mission control.** Ask PathPro (on Backboard) answers "why is this street high?" or "how was the model tested?" from PathPro's own model card and docs, plus the street, route, or area on screen and live conditions. Every answer is checked before it is shown: any number that isn't in the docs or the on-screen evidence, or any crime framing, and the answer is replaced with a pointer to the model card.
- **Engine-out capability.** Explanations fail over from Grok to Groq to Gemini to a deterministic template. Voice fails over from Grok Voice to ElevenLabs to the device. The offline demo (`?demo=1`) keeps flying with no network at all.
- **Test like you fly.** I trained on 2020–23, tested on 2024, and report 95% spatial-block confidence intervals. About 1,506 automated tests run, including end-to-end GPS navigation.
- **Reusable by design.** A new city needs one coverage polygon plus its public crash layers. The pipeline, models, and app fly again unchanged.
- **The mission is public health.** Traffic crashes kill more than 7,000 people walking in the U.S. each year. PathPro gives walkers a lower-risk way home tonight, and gives cities a ranked, visual plan for where fixes reach the most future crashes.

## How I built it

- **Data:** about 250k public crash records from 8 ArcGIS layers (ARC, City of Atlanta, Central Atlanta Progress, Georgia Tech, 2013–2026).
  - I merged duplicates across sources, dropped personal fields, and snapped crashes to OpenStreetMap road segments.
  - I found a source storing local time as UTC by checking it against its reported light condition; agreement went from 60% to 94% after the fix.
  - Features: StreetLight pedestrian activity, 2023 traffic volumes, speed limits, lanes, bus boardings, sidewalks, signals, and crossings. No demographic or income features.
- **ML:** an exposure-aware safety performance function (Poisson GLM + monotone LightGBM, spatial-block cross-validation), blended with each street's history by Empirical Bayes. A multi-task Poisson GLM learns how risk shifts by hour, day, light, and rain. Every score splits exactly into plain-language factors.
- **Evaluation:** trained on 2020–23 and tested on 2024.
  - The 10% of street length PathPro ranks highest held **74.3%** of 2024 pedestrian crashes (95% spatial-block CI 70.5–78.3%).
  - That compares with 49.8% for ranking by past crashes, 53.8% for the City's High Injury Network, and 11.9% for a random ranking. ROC-AUC is 0.89.
  - PathPro's score also captures more on the City High Injury Network's own share of street length.
  - **Ride model** (174 cyclist crashes in 2024): **69.9%** of them fell on the 10% of street length it ranks highest (95% CI 64.0–76.1%). That compares with 43.6% for the High Injury Network, 30.4% for past bike crashes, and 12.0% at random. On the 2023 validation year it scored 69.0%.
    - It is trained on pedestrian + cyclist crashes pooled, because 2023 validation favored that over cyclist-only labels, but it is scored on cyclist crashes only. So I claim ranking, not calibrated cyclist counts.
    - Exposure uses a Strava proxy. Removing Strava gives 69.5%.
- **Personal safety, with fairness designed in:**
  - Crime is **never** used in routing or in the traffic model. A test multiplies crime counts by 1,000 and checks that routes don't change.
  - The layer covers crimes against persons only (homicide, robbery, aggravated assault, simple assault). It excludes residences, jails, and shelters, fetches no addresses or victim fields, and aggregates to H3 hexes by time of day.
  - Bands use an Empirical-Bayes rate per unit of foot traffic, so an area with no reports is never marked "higher". A fairness note always sits beside the layer.
  - Lighting is known for only about 4% of streets. PathPro says so, and unknown stays unknown rather than "dark".
- **Sponsors and the job each one does:**
  - **Vultr:** the whole app runs on a Vultr VM in Atlanta, with Caddy (automatic HTTPS), a hardened systemd service, and a firewall. One command provisions and deploys it.
  - **.tech:** **pathpro.tech**, read as "path protect"; the .tech finishes the word.
  - **Tiger Data** (TimescaleDB + PostGIS): the crash hypertable and hourly continuous aggregate behind "when crashes happened here", plus geometry and the versioned risk grid.
  - **MongoDB Atlas:**
    - Community reports use a 2dsphere viewport query, a 14-day TTL, atomic upserts that turn repeat reports into confirmations, and an aggregation summary.
    - Share my walk uses a TTL of 6 hours after the last update, hashed owner tokens, and optimistic-concurrency position updates.
  - **ElevenLabs:** spoken explanations and navigation alerts, as the backup to Grok Voice.
  - **Grok (xAI):** first in the explanation chain, Grok Voice callouts, and Grok Imagine street redesigns.
  - **Groq** (gpt-oss-120b/20b) and **Gemini** as fallbacks: grounded explanations. A validator rejects any sentence with a number not in the evidence, and any crime framing. **Gemini** (multimodal) also reviews every Grok Imagine illustration before it is shown: it confirms which planned fixes appear and rejects images with readable text, logos, or identifiable faces.
  - **Backboard:** Ask PathPro <!-- gated: after deploy -->. A Backboard assistant holds PathPro's curated docs (model card, metrics, safety sources, decision log, data and models, judge Q&A). Public questions use read-only memory, so no visitor can change what it knows. Memory is opt-in and private: turning it on clones the assistant for that browser only, it keeps only stated travel preferences (never places), questions about a street, route, or area never write it, and "Forget me" deletes it. Every answer is validated (no number that isn't in the docs or the on-screen evidence, no crime framing, no outside links) with a fixed fallback, and each visitor gets 20 questions a day.
- **App:** React + MapLibre + deck.gl, FastAPI, and scipy Dijkstra routing. Both route plans take about 150 ms at the median.
- **Engineering:** test-first throughout (RED and GREEN commits), with independent code, ML, and security review passes.
  - About 1,506 automated tests: 237 data, 628 API, 622 web, and 19 end-to-end, including an offline demo and a GPS navigation flow.
  - 90%+ coverage per package.
- **AI tools (disclosed):**
  - AI tools used: AI coding assistants (Claude Code, Cursor) during development; Grok models, Grok Imagine, Grok Voice, Gemini and Backboard in the product. I followed a test-first workflow with independent review.
  - Scope, product decisions (including the safety layer and its safeguards), and review were mine.
  - Frameworks and datasets are credited in the README and in docs/safety_sources.md.

## Impact and ROI

- **For cities:** with the same budget spent on 10% of street length, PathPro's ranking reaches **74.3%** of the next year's pedestrian crashes, against **53.8%** for the City's High Injury Network. That is **about 38% more crashes reached for the same spend**. For cyclists it is 69.9% against 43.6%, about 60% more.
- **For people:** on the Klaus → Midtown MARTA night walk, **+4 minutes buys 54% less traffic-risk exposure**. By bike from Georgia Tech to Inman Park, +4 minutes buys 72% less.
- **For scale:** a new city needs one coverage polygon plus its public crash layers. The pipeline, models, and app carry over.

## Challenges I ran into

- **Missing roads in the walk graph.** Most Midtown roads are missing from OpenStreetMap's walk network because their sidewalks are mapped separately. A third of pedestrian crashes couldn't snap until I modeled risk on road centerlines and let sidewalks inherit it (snap rate 66% → 96%).
- **Compressed route scores.** Every Midtown street is top-quartile at night, so whole-route scores looked alike. I rebuilt routing around risk density and total exposure.
- **"Not intuitive."** My first UI stacked four panels over the map on a phone. I rebuilt it: map-first, GPS by default, a Google-Maps-style route sheet, walking navigation, and a proper desktop layout.
- **Adding safety without stigma.** Terciles on raw crime counts marked 563 areas with no reports as "higher", because few people walk there. I switched to an exposure-normalized Empirical-Bayes posterior and kept crime out of routing entirely.
- **A drawing bug hiding in plain sight.** OSMnx stores most edge geometries in the opposite direction, so every other edge was drawn backwards. Routes looked zigzagged and navigation overstated distance by 1.6×. I fixed the orientation and added a regression test.
- **Honest statistics.** The ML review pass caught bootstrap intervals that were too narrow (they now resample spatial blocks) and a weak temporal baseline, which revealed that rain adds little. I report it.
- **Memory without a privacy leak.** The first version of Ask PathPro's opt-in memory could have remembered streets from "Ask about this street" questions. Now only plain questions can write memory, and the memory keeps stated travel preferences only.

## Accomplishments I'm proud of

- The model beats the City of Atlanta's own High Injury Network on future crashes, with confidence intervals shown.
- Every number on screen traces to the model. The factor bars add up exactly, and the AI can't invent numbers.
- A mentor's "why would anybody use this" became a two-tap flow with GPS, navigation, and learned routines in one afternoon.
- The personal-safety layer is useful and honest about its limits, and it never routes around neighborhoods.
- It stays usable when the weather API, the LLM, a database, GPS, or the Wi-Fi fails.

## What I learned

- Most of the work is data plumbing and honest evaluation, not model choice.
- Exposure bias is real in both crash and crime data. Normalizing by foot traffic and saying so makes the claims stronger.
- Watching one real person use the app on a phone taught me more than any test.

## What's next for PathPro

- Wheelchair and stroller profiles
- Citywide lighting data through a partnership with the City or Georgia Power
- Push notifications and background location for navigation
- A Vision Zero planning dashboard for the city and campus, pairing top-ranked streets with Grok Imagine redesigns
- New cities by swapping one coverage polygon

## Built with

Grok (xAI) · Grok Imagine · Grok Voice · Backboard · Python · FastAPI · LightGBM · scikit-learn · statsmodels · OSMnx · GeoPandas · H3 · SciPy · React · TypeScript · Vite · MapLibre GL · deck.gl · Groq · Gemini API · ElevenLabs · Tiger Data (TimescaleDB, PostGIS) · MongoDB Atlas · Vultr · Caddy · Playwright
