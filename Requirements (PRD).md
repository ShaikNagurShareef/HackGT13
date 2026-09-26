# PathPulse — Product Requirements

Sep 25, 2026 · @Nagur Shareef Shaik

## 1. Overview

**Product:** PathPulse — a predictive traffic-risk map and risk-aware walking router for Atlanta.

**Tagline:** *See traffic risk before you walk into it.*

**Event context:** HackGT 13, Oracle of the Deep (ML/AI + visualization) track. Hacking window runs Friday Sep 25, 8 PM → Sunday Sep 27, 8 AM; Expo Sunday 9:30–11:00 AM in the Klaus Atrium; Devpost closes 12:00 PM (target submission 7:30 AM).

### 1.1 Problem

Navigation apps optimize one number: travel time. They are silent about the fact that some intersections and corridors carry a concentrated history of pedestrian-involved crashes, and that this risk shifts sharply with darkness, rain, and time of week. A student leaving Klaus at 11 PM sees two routes that look equivalent on a map but are not equivalent in exposure.

### 1.2 Product thesis

PathPulse turns public crash records into a street-level, time-varying risk surface, lets people *see* how that surface changes through the day and weather (Risk Tides), and offers a route that trades a small amount of time for a large reduction in exposure. Every score is explainable: a trained model produces it, SHAP decomposes it, and an LLM translates that evidence into plain language. The LLM never produces a risk number.

**Scope of "risk":** PathPulse models *traffic* risk to pedestrians — the historical and predicted likelihood of vehicle–pedestrian crashes. It does not model crime or personal security, and the product must say so wherever a user might assume otherwise (see §7 copy rules).

### 1.3 Goals

| ID | Goal | Measure |
| --- | --- | --- |
| G1 | Make invisible, time-dependent traffic risk visible | Risk Tides animates 24 hourly frames × dry/wet with no perceptible lag |
| G2 | Offer a meaningfully lower-exposure route at a small time cost | Demo route: ≥30% reduction in meters on high-risk segments for ≤ +25% walk time |
| G3 | Make every score explainable and trustworthy | 100% of segment and route scores have SHAP contributions + a grounded explanation |
| G4 | Beat a naive baseline with real ML | Model outperforms a "historical count only" baseline on temporal holdout (top-decile capture, Poisson deviance) |
| G5 | Deliver a reliable 3-minute demo | Full demo path works offline-cached if venue Wi-Fi fails |

### 1.4 Non-goals (this weekend)

Crime or personal-safety prediction; native mobile apps; crowdsourced reporting; computer vision on street imagery; turn-by-turn navigation with live GPS re-routing; coverage beyond the defined Atlanta core area; driver or transit routing. These are listed in §9 as future work.

### 1.5 Success metrics

| Type | Metric | Target |
| --- | --- | --- |
| Model | Top-decile capture on holdout (share of held-out pedestrian crashes falling in the top 10% of predicted segment-hours) | ≥ 2× the random baseline and above the count-only baseline |
| Model | Calibration (predicted vs observed counts by decile) | Monotonic, within ±25% per decile |
| Product | Route request p95 latency | < 1.5 s |
| Product | Risk Tides frame swap | < 100 ms after first load |
| Product | Explanation latency (LLM) | < 3 s, with instant template fallback |
| Demo | Judge "wow" moment | Reached within the first 30 seconds of the demo |

## 2. Users and scenarios

### 2.1 Personas

| Persona | Context | What they need from PathPulse |
| --- | --- | --- |
| **Night walker** (primary) — GT student walking between campus, Home Park, Midtown, and MARTA after dark | Time-pressed, on a phone, often in low light and sometimes in rain | A quick, glanceable "which way is lower risk right now" answer and a hands-free heads-up near hotspots |
| **Planner** — student or parent choosing an apartment, commute, or event route in advance | On a laptop, exploring, comparing times and conditions | Explore the map at different hours and weather, compare routes for a future departure time |
| **Campus safety / city analyst** (secondary) | Looking for patterns, not a route | See where and when risk concentrates, understand *why* via factor breakdowns |
| **Hackathon judge** (demo persona) | 3–5 minutes, skeptical of AI hype | See real data, real ML, a visible "wow" moment, and an honest explanation of what the model can and cannot claim |

### 2.2 Core scenarios

**S1 — Walk home tonight.** A student enters "Klaus → Midtown MARTA", departure *Now* (10:30 PM, light rain). PathPulse shows the fastest route (18 min, risk 74) and a PathPulse route (21 min, risk 31), explains the difference in one sentence, and can speak alerts on approach to high-risk segments.

**S2 — Explore the tides.** A user drags the timeline from 2 PM to 11 PM and toggles rain, watching corridors light up. They tap a glowing intersection and see its score, top contributing factors, and a plain-English explanation.

**S3 — Plan ahead.** A user sets departure to Saturday 1 AM. PathPulse uses the forecast if available, otherwise asks the user to choose dry or wet, and labels the assumption.

**S4 — Nothing better exists.** For some trips the fastest route is already the lower-risk choice. PathPulse says so plainly rather than inventing a detour.

**S5 — Outside coverage.** A user searches a destination in Decatur. PathPulse explains the coverage area and offers the nearest covered point or a map-only view.

## 3. User journeys and screen flow

PathPulse is a single-page app with one persistent map and four modes layered on top of it. There is no splash screen and no login wall: the map with live risk is the first thing a user sees.

| Screen / mode | Entry | What's on screen | Exits |
| --- | --- | --- | --- |
| **First run** | First visit (per browser) | Map loads behind a one-card intro: what PathPulse shows, that it models *traffic* risk, data-through date, "Got it" | Explore |
| **Explore** (default) | App load, or clearing a route | Full-screen risk map at the current hour and live conditions; Risk Tides timeline docked at the bottom; conditions chip (Live · Dry · Wet); search bar at top; legend | Route (search), Segment detail (tap) |
| **Route compare** | Origin + destination set | Two routes drawn (fastest in neutral grey, PathPulse in teal), comparison card with time, risk score, high-risk meters, and a one-line explanation; departure-time picker | Walk (Start), Segment detail (tap on route), Explore (clear) |
| **Segment detail** | Tap a segment, intersection, or hotspot | Bottom sheet: risk score dial, confidence badge, factor contribution bars, 1–3 sentence explanation, crash history summary (counts by light/surface, date range), "Listen" | Back to previous mode |
| **Walk** (P1) | "Start walk" on the PathPulse route | Simplified map following the user, next high-risk segment distance, voice alerts on/off, end walk | Route compare (end) |
| **About / data** | Info icon | Methodology in plain words, data sources and freshness, limitations, emergency numbers | Back |

### 3.1 Primary journey (S1)

The user taps the search bar, types a destination, and picks a suggestion. Origin defaults to device location if permission is granted, otherwise the search bar asks for an origin with Klaus Building as a suggested chip. Departure defaults to *Now*. Within 1.5 s the comparison card appears and the map animates the two routes drawing from origin to destination. Tapping the PathPulse route highlights the hotspots it avoids; tapping a red segment on the fastest route opens Segment detail explaining why that stretch scores high. "Start walk" enters Walk mode and, after an explicit tap to enable audio, speaks alerts.

### 3.2 Exploration journey (S2)

The user drags the Risk Tides handle or presses play. Frames interpolate hour to hour; the hour label and a small sun/moon indicator update. Switching Dry ↔ Wet crossfades the risk layer. The legend stays fixed on a citywide scale so frames are comparable across hours and conditions.

### 3.3 State that must survive navigation

Origin, destination, departure time, conditions override, and selected segment are encoded in the URL (`?from=…&to=…&t=…&cond=…&seg=…`) so any view is shareable, refresh-safe, and reproducible in the demo.

## 4. Functional requirements

Priorities: **P0** = required for the demo (MVP), **P1** = strong polish if time allows by Saturday night, **P2** = stretch, build only after feature freeze criteria are met. Every P0 has an acceptance criterion a teammate can check in under a minute.

### 4.1 Map and base experience (MAP)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| MAP-01 | Load a full-screen dark basemap centered on Georgia Tech / Midtown with the coverage boundary subtly outlined | P0 | Map interactive < 2.5 s on venue Wi-Fi; boundary visible at zoom ≤ 13 |
| MAP-02 | Render every covered street segment colored by risk for the selected hour and condition | P0 | All segments render; color matches the legend scale; no segment is uncolored |
| MAP-03 | Render intersection hotspots as glowing points sized by risk, visible above segments | P0 | Top 5% intersections render as hotspots; tap target ≥ 44 px |
| MAP-04 | Persistent legend with a fixed citywide 0–100 scale and "limited data" pattern | P0 | Legend never rescales between frames |
| MAP-05 | Auto-switch basemap to light theme during daylight hours of the selected time, dark at night | P1 | Theme follows sunrise/sunset for the selected date |
| MAP-06 | "Locate me" control, shown only when geolocation is available | P1 | Denied permission hides control and shows no error loop |

### 4.2 Risk Tides timeline (TIDE)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| TIDE-01 | Bottom timeline spanning 24 hours in 1-hour steps, labeled 6 AM → 2 AM style with sun/moon markers at sunset/sunrise | P0 | Dragging updates the map within 100 ms per frame |
| TIDE-02 | Play/pause animation cycling hours at \~1 frame/sec with smooth color interpolation | P0 | Animation runs 60 fps on a mid-range laptop |
| TIDE-03 | Day-of-week selector (weekday / Friday / Saturday / Sunday groups) | P1 | Changing day swaps frames without reload |
| TIDE-04 | Keyboard and screen-reader operable slider (arrow keys, labelled value) | P0 | Passes keyboard-only test; value announced as "10 PM, wet, citywide median risk 42" |
| TIDE-05 | Sparkline above the slider showing citywide mean risk by hour | P1 | Sparkline updates with condition toggle |

### 4.3 Conditions (COND)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| COND-01 | "Live" condition pulls current and hourly forecast precipitation and visibility for the coverage centroid | P0 | Live chip shows icon + "Light rain · updated 4 min ago" |
| COND-02 | Manual override: Dry / Wet chips always available | P0 | Override persists in URL; Live resumes when selected |
| COND-03 | Light condition is derived from the selected time and computed sunrise/sunset, never from the user | P0 | 7 PM in September renders as dusk/dark correctly |
| COND-04 | For departure times beyond the forecast horizon or in the past, fall back to override with a visible label "Assuming dry — no forecast for this time" | P0 | Label present whenever Live data is not used |

### 4.4 Search and places (SRCH)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| SRCH-01 | Autocomplete for origin and destination biased to the coverage area | P0 | "MARTA" surfaces Midtown, North Ave, Arts Center stations first |
| SRCH-02 | Curated quick picks: Klaus, Tech Square, Midtown MARTA, North Ave MARTA, Home Park, Georgia Tech Hotel | P0 | One tap sets the field |
| SRCH-03 | Origin defaults to device location when permitted and inside coverage | P0 | Outside coverage → origin left empty with explanation |
| SRCH-04 | Swap origin/destination control | P1 | Swap re-requests routes |
| SRCH-05 | Tap-and-hold (desktop: right-click) on map to set origin/destination | P1 | Pin drops and reverse-geocodes |

### 4.5 Routing and comparison (RTE)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| RTE-01 | Compute the fastest walking route and a risk-aware PathPulse route on the same pedestrian network | P0 | Both routes returned in one response, p95 < 1.5 s |
| RTE-02 | PathPulse route must respect a detour budget: ≤ fastest × 1.25 or fastest + 6 min, whichever is smaller | P0 | No returned route violates the budget |
| RTE-03 | If no candidate lowers route risk by ≥ 10 points, show a single route with "The fastest route is already the lower-risk option" | P0 | Verified on a short campus trip |
| RTE-04 | Comparison card: walk time, distance, route risk (0–100), meters on high-risk segments, % reduction | P0 | Numbers match backend response exactly |
| RTE-05 | Departure time picker (Now, +15 min, +1 h, custom) that re-scores routes | P0 | Changing time updates both routes and the map frame |
| RTE-06 | Highlight the specific hotspots the PathPulse route avoids, with a count ("Avoids 3 high-risk crossings") | P1 | Tapping the count flies to each |
| RTE-07 | Up to one additional alternative ("Balanced") when meaningfully different | P2 | Shown only if it differs by ≥ 15% of path length |

### 4.6 Explainability (EXP)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| EXP-01 | Segment detail shows score, top 5 factor contributions (signed), and a remainder bar so parts sum to the displayed score | P0 | Displayed contributions sum to score ±1 |
| EXP-02 | Confidence badge (High / Medium / Limited data) based on historical observations near the segment | P0 | Segments with < 3 nearby observations show Limited data |
| EXP-03 | Crash history summary: count, pedestrian-involved count, share after dark, share on wet surface, data date range | P0 | Numbers trace to stored aggregates |
| EXP-04 | Route-level explanation: which segments drive the fastest route's score and what the PathPulse route avoids | P0 | Explanation references at most 3 named streets/intersections |
| EXP-05 | "How is this calculated?" link to About methodology | P0 | Link present in every detail sheet |

### 4.7 GenAI explanations (GEN)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| GEN-01 | Generate 1–3 sentence explanations from structured evidence only (score, SHAP contributions, history stats, route deltas) | P0 | Prompt contains no free-form user text |
| GEN-02 | Validate output: every number in the text must appear in the evidence payload; banned phrases rejected ("safe", "guaranteed", "crime", "dangerous neighborhood") | P0 | Invalid output replaced by template |
| GEN-03 | Deterministic template fallback when the LLM times out (> 3 s), errors, or fails validation | P0 | Explanation always renders |
| GEN-04 | Cache explanations by (entity, hour, condition, model version) | P0 | Repeat taps return in < 50 ms |
| GEN-05 | Stream text into the sheet so first words appear < 1 s | P1 | Visible streaming |

### 4.8 Voice and Walk mode (VOX)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| VOX-01 | "Listen" button in Segment detail and comparison card reads the explanation aloud | P1 | Audio starts < 1.5 s after tap |
| VOX-02 | Walk mode speaks an alert \~60 m before entering a segment in the top risk decile, at most once per segment and no more than once every 45 s | P1 | Simulated walk triggers expected alerts only |
| VOX-03 | Audio only after an explicit user gesture; persistent mute toggle | P0 (if VOX ships) | No autoplay attempts |
| VOX-04 | Browser speech synthesis fallback if the voice API fails | P1 | Alert still audible offline |
| VOX-05 | Simulated walk ("Preview walk") for the demo that moves a marker along the route at 5× speed | P1 | Deterministic, no GPS required |

### 4.9 Data and model operations (DATA)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| DATA-01 | Ingest GDOT crash records for the coverage area, clean, dedupe, and snap to segments/intersections | P0 | Ingestion report: records in, dropped by reason, snapped |
| DATA-02 | Build the pedestrian network and segment table from OpenStreetMap | P0 | Graph connected within coverage (largest component ≥ 98% of nodes) |
| DATA-03 | Train, evaluate, and version the risk model; persist metrics with the model | P0 | `model_version` visible in About |
| DATA-04 | Precompute risk for every segment × hour-of-week group × condition and load into the database | P0 | Row count = segments × hours × conditions |
| DATA-05 | Show "Crash data through \<date>" in About and first-run card | P0 | Date derived from max crash date |

### 4.10 Trust, about, and safety (TRUST)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| TRUST-01 | About page: methodology in plain language, limitations, sources, model version | P0 | Readable in < 2 min |
| TRUST-02 | Persistent, unobtrusive note: "Traffic risk estimate from historical crashes. Always stay alert." | P0 | Visible in Route compare and Walk |
| TRUST-03 | Emergency access: 911 and Georgia Tech Police (404-894-2500) in About and Walk mode menu | P0 | Tap-to-call on mobile |

### 4.11 Accounts (ACCT) — optional, Auth0

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| ACCT-01 | Guest mode is the default; every P0 feature works without signing in | P0 | No login prompts in the demo path |
| ACCT-02 | Sign in with Auth0 to save places (Home, Work) and default preferences (voice on, detour budget) | P2 | Saved places appear as quick picks |

### 4.12 City Pulse — citywide traffic risk (CITY)

Traffic risk only; the same model family as street segments, aggregated to H3 resolution-9 hexes across the City of Atlanta. Never crime.

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| CITY-01 | Hex layer covering the City of Atlanta, colored on the same 0–100 citywide scale, animated by Risk Tides | P1 | Zooming out below z12 (or tapping "City") crossfades segments → hexes; timeline and Dry/Wet drive hex frames |
| CITY-02 | Area card for any Atlanta address: score, band, top factors, crash history, confidence | P1 | Searching "West End" shows the card within 1 s |
| CITY-03 | Out-of-coverage destinations inside Atlanta show the area card plus "Street-level routing covers Midtown, GT, and Downtown" | P1 | Replaces the EC-01 dead end for in-city points |
| CITY-04 | Hex factor contributions sum to the displayed score | P1 | Same ±1 rule as EXP-01 |

### 4.13 Demo mode (DEMO)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| DEMO-01 | `?demo=1` loads the scripted scenario (Klaus → Midtown MARTA, 10:30 PM, wet) from cached responses | P0 | Works with network disabled after first load |
| DEMO-02 | Hidden keyboard shortcuts: `T` jumps timeline to 10:30 PM, `R` toggles rain, `D` loads the demo route | P1 | Shortcuts disabled outside demo mode |

## 5. Edge cases and error states

The rule for every row: the user always sees a usable map, an honest statement of what PathPulse assumed or could not do, and one clear next action. No blank panels, no spinners longer than 3 s without text, no raw error codes.

### 5.1 Search, places, and location

| ID | Situation | Expected behavior | Copy |
| --- | --- | --- | --- |
| EC-01 | Destination outside coverage | Keep the pin, don't route; offer nearest covered point along the straight line | "PathPulse covers Midtown, Georgia Tech, and Downtown for now. Route to the edge of coverage?" |
| EC-02 | Origin and destination identical or < 60 m apart | No routing; show the segment detail of the location instead | "You're already there — here's the risk on this block." |
| EC-03 | Geocoder returns no results | Keep typed text, suggest quick picks | "No match nearby. Try a building or street name." |
| EC-04 | Ambiguous result (e.g., "Starbucks") | Show up to 5 results ranked by distance with addresses | — |
| EC-05 | Location permission denied or unavailable | Hide Locate control; origin field focused with quick picks | "Location is off — pick a starting point." |
| EC-06 | GPS accuracy worse than 100 m | Use location but show an accuracy ring; do not trigger voice alerts | "Location is approximate." |
| EC-07 | Point lands on a freeway, rail line, or private area with no walkable edge | Snap to the nearest walkable node within 150 m; beyond that, ask user to move the pin | "We moved your start to the nearest sidewalk." |
| EC-08 | Start and end in disconnected network components | Return error with the gap location highlighted | "No walkable connection found between these points." |

### 5.2 Routing

| ID | Situation | Expected behavior | Copy |
| --- | --- | --- | --- |
| EC-10 | Both routes are identical or risk difference < 10 points | Single route, positive framing (RTE-03) | "The fastest route is already the lower-risk option." |
| EC-11 | Lowest-risk candidate exceeds the detour budget | Return best route within budget; mention the trade-off exists | "A lower-risk route exists but adds 11 min. Showing the best option under 6 extra min." |
| EC-12 | Every candidate crosses the same unavoidable hotspot (e.g., only bridge over I-75/85) | Route normally; flag the unavoidable segment specifically | "Both routes cross 5th St bridge — highest-risk stretch, about 90 m." |
| EC-13 | Very long trip (> 5 km or > 60 min walk) | Allow but warn; suggest transit | "This is a long walk. Consider MARTA for part of it." |
| EC-14 | Route passes through segments marked Limited data | Count them separately; never treat as zero risk | "Part of this route has limited crash history; score is less certain." |
| EC-15 | Routing backend timeout (> 3 s) | Retry once, then show map-only view with a retry button | "Couldn't compute routes. Retry" |

### 5.3 Time and conditions

| ID | Situation | Expected behavior | Copy |
| --- | --- | --- | --- |
| EC-20 | Departure beyond forecast horizon, or in the past | Use manual condition; label assumption (COND-04) | "Assuming dry — no forecast for this time." |
| EC-21 | Weather API unavailable | Serve last cached value if < 60 min old, else default Dry + banner | "Live weather unavailable — using dry conditions." |
| EC-22 | Daylight-saving transitions (Nov 1, 2026 in Atlanta) | All times computed in America/New\_York; the repeated 1 AM hour maps to the same hour-of-week bucket | — |
| EC-23 | Departure crosses midnight or a light transition mid-walk | Score each segment at its estimated traversal time, not departure time | — |
| EC-24 | Snow, ice, or fog | Model only knows dry/wet; map snow/ice to wet and show a stronger caution | "Icy conditions are rarer in our data — use extra caution." |
| EC-25 | User's device clock or timezone differs from Atlanta | Always display and compute Atlanta local time; show "ET" suffix | — |

### 5.4 Data and model

| ID | Situation | Expected behavior | Copy |
| --- | --- | --- | --- |
| EC-30 | Segment with zero historical crashes | Score comes from the model's structural features with shrinkage; badge = Limited data; never 0 | "No recorded crashes here — estimate based on street characteristics." |
| EC-31 | Crash records with missing, (0,0), or out-of-state coordinates | Drop during ingestion; counted in ingestion report | — |
| EC-32 | Crash snaps > 30 m from any segment | Drop; counted | — |
| EC-33 | Duplicate records (same time, location, attributes) | Deduplicate on normalized key | — |
| EC-34 | Recent data lag (last months incomplete) | Train and evaluate on complete periods only; show data-through date | "Crash data through \<date>." |
| EC-35 | Street changed since the crashes (road diet, new signal) | Known limitation; disclosed in About; P2 feedback link | — |
| EC-36 | Model file or precomputed table missing at startup | Health check fails; deploy blocked; demo mode still works from cache | — |

### 5.5 GenAI and voice

| ID | Situation | Expected behavior | Copy |
| --- | --- | --- | --- |
| EC-40 | LLM timeout, rate limit, or 5xx | Instant template explanation (GEN-03); log | — (user sees a normal explanation) |
| EC-41 | LLM output fails validation (unknown numbers, banned words, > 3 sentences) | Discard, use template; log for prompt fixing | — |
| EC-42 | LLM mentions crime, demographics, or neighborhoods | Blocked by validator | — |
| EC-43 | Browser blocks audio autoplay | Show "Tap to enable voice alerts"; never retry silently | "Tap to turn on voice alerts." |
| EC-44 | Voice API fails mid-walk | Fall back to browser speech synthesis; if unavailable, vibrate + visual banner | — |
| EC-45 | Several hotspots within 100 m of each other | Merge into one alert covering the stretch | "Next 200 m has two high-risk crossings." |
| EC-46 | User deviates from route in Walk mode | Stop route alerts, keep proximity alerts to any top-decile segment; offer re-route | "You've left the route. Re-route?" |

### 5.6 Network, device, and accessibility

| ID | Situation | Expected behavior | Copy |
| --- | --- | --- | --- |
| EC-50 | Slow or dropped connection after load | Map and last frames stay usable; routing disabled with retry | "You're offline. Map still works; routing needs a connection." |
| EC-51 | WebGL unavailable | Static image fallback of the current frame + text route summary | "Your browser can't show the live map." |
| EC-52 | Small phone viewport (≤ 360 px) | Timeline collapses to a compact scrubber; detail sheet full-height | — |
| EC-53 | User prefers reduced motion | Disable tide animation interpolation and route draw animation | — |
| EC-54 | Color-vision deficiency | Palette is luminance-ordered; high-risk segments also thicker; legend has numbers | — |
| EC-55 | Screen reader user | Route compare announced as text; map not required to complete a route query | — |
| EC-56 | Rapid slider scrubbing | Frames prefetched; rendering throttled to animation frames; no network per tick | — |
| EC-57 | Many concurrent judges hitting the demo URL | Precomputed frames served from CDN/static; LLM explanations cached | — |

### 5.7 Interpretation and misuse

| ID | Situation | Expected behavior |
| --- | --- | --- |
| EC-60 | User reads "risk" as crime/personal safety | First-run card, About, and the TRUST-02 note all say "traffic risk"; LLM is forbidden from crime framing |
| EC-61 | User treats a low score as "safe" | Never display the word "safe"; low scores read "Lower traffic risk" |
| EC-62 | Stigmatizing an area | No area or neighborhood labels on risk; explanations reference street features and conditions, not places' people |
| EC-63 | Someone in immediate danger | Emergency numbers are always one tap away (TRUST-03); PathPulse is not an emergency service |

## 6. Non-functional requirements

| Area | ID | Requirement |
| --- | --- | --- |
| Performance | NFR-01 | Map interactive < 2.5 s on first load; segment geometry ≤ 3 MB compressed |
| Performance | NFR-02 | All risk frames for a condition (24 × one byte per segment) fetched once; frame swap < 100 ms |
| Performance | NFR-03 | `POST /routes` p95 < 1.5 s; explanation first token < 1 s, full < 3 s |
| Reliability | NFR-04 | No single external dependency (LLM, weather, voice, geocoder) can break the core flow; each has a fallback (§5) |
| Reliability | NFR-05 | Demo mode works fully from cached responses with the network disabled |
| Reliability | NFR-06 | Backend exposes `/healthz` covering DB, model, and precompute readiness |
| Accessibility | NFR-07 | WCAG 2.1 AA contrast for all text; tap targets ≥ 44 px; keyboard operable; `prefers-reduced-motion` respected |
| Accessibility | NFR-08 | Color is never the only carrier of risk: numbers in legend and detail, line width scales with risk |
| Privacy | NFR-09 | Guest location never stored server-side; request logs round coordinates to 3 decimals (\~100 m) and drop them after the event |
| Privacy | NFR-10 | No third-party analytics; no tracking cookies |
| Security | NFR-11 | API keys server-side only; Mapbox public token URL-restricted to the app domain; CORS locked to the app origin; basic rate limit (60 req/min/IP) |
| Responsible AI | NFR-12 | LLM never generates or alters a risk number; outputs validated against evidence (GEN-02) |
| Responsible AI | NFR-13 | Model card in About: data period, features, holdout metrics, known biases (exposure bias, reporting bias, road changes) |
| Responsible AI | NFR-14 | No demographic, income, or crime features in the model |
| Maintainability | NFR-15 | Every score carries `model_version`; precompute tables keyed by version |
| Portability | NFR-16 | Coverage area defined by a single config polygon so the city can change without code changes |

## 7. UX and visual design principles

### 7.1 Principles

**The map is the product.** Chrome is minimal and translucent; panels float over the map and never cover more than 40% of it on desktop or 55% on mobile.

**One question per screen.** Explore answers "where and when is risk high?"; Route compare answers "which way should I walk?"; Segment detail answers "why?". Nothing else competes.

**Numbers are honest and consistent.** One 0–100 citywide scale everywhere. Scores are rounded to integers; percentages to whole numbers. Anything uncertain is labeled, never hidden.

**Calm, not alarming.** The product informs; it does not frighten. Motion is slow and tidal, not flashing. High risk glows; it does not pulse or blink.

### 7.2 Visual language ("Deep water")

The theme borrows from HackGT's Seaside setting and the track name. The night basemap is deep navy; risk is rendered as light on dark water. The risk scale is a perceptually uniform, luminance-ordered ramp from deep teal (lower) through sand/amber to coral and hot magenta (higher), so it reads correctly in grayscale and for common color-vision deficiencies. Line width grows with risk (1.5 px → 5 px at zoom 15). Hotspots use an additive glow. The PathPulse route is a bright teal line with a slow moving "current" animation; the fastest route is neutral grey so it reads as the baseline, not the villain.

Type: Inter (UI) with tabular numerals for all scores and times. Risk score dial uses a large numeric (48 px) with the band word beneath ("Elevated").

### 7.3 Risk bands

| Score | Band label | Use |
| --- | --- | --- |
| 0–24 | Lower | Default calm state |
| 25–49 | Moderate | — |
| 50–74 | Elevated | Shown on map; not counted as high-risk exposure |
| 75–100 | High | Counted as "high-risk meters" in route exposure (RTE-04); scores ≥ 90 are eligible for voice alerts (VOX-02) |

Bands are fixed labels on the citywide percentile scale (score = percentile of predicted rate across all segment-hours for the model version), so "High" always means top quartile of the city.

### 7.4 Copy rules

Say "traffic risk", "lower-risk route", "historical crashes", "estimate". Never say "safe", "safest", "dangerous area", "bad neighborhood", "crime", or "guaranteed". Refer to places by street and intersection names, not neighborhoods. Explanations name at most three factors and one concrete action. Time costs are always stated next to benefits ("+3 min, 58% less high-risk walking").

### 7.5 Motion

Route draw: 700 ms ease-out from origin. Frame change: 400 ms color interpolation. Detail sheet: 250 ms spring. All disabled under reduced motion (EC-53).

## 8. Sponsor integrations and judging map

Each sponsor technology must do a job the product genuinely needs, and each must be *visible* in the demo at the moment it matters. Confirm which MLH prizes are live for HackGT 13 at the MLH table before relying on them.

| Sponsor / prize | Role in PathPulse | Requirement | Where judges see it |
| --- | --- | --- | --- |
| **Oracle of the Deep** (track) | Whole product | ML model + SHAP + Risk Tides visualization | Entire demo; model card in About |
| **Aramco — A Marina's Mission** (social-good track) | Whole product: pedestrian deaths are a public-health problem | Impact framing in pitch and Devpost; cite Atlanta Vision Zero numbers | Opening line of the pitch |
| **Best Overall** | Whole product | — | — |
| **Groq** (LLM, primary) | Generates grounded explanations (GEN-01…05) with `openai/gpt-oss-120b` → `gpt-oss-20b` | Provider chain Groq → Gemini → template; prompt and validator in repo | Segment detail explanation |
| **Gemini API** (MLH, confirm live) | Secondary LLM in the explanation chain | Confirm the prize is live with the MLH coach | Architecture slide |
| **ElevenLabs** (MLH) | Speaks "Listen" and Walk-mode alerts (VOX-01…05) | Browser speech-synthesis fallback; pre-generated demo clips | "Listen"; Preview walk |
| **Tiger Data** (MLH) | System of record: crash hypertable, hourly continuous aggregates, PostGIS geometry, precomputed risk grid | Crash history stats in EXP-03 come from continuous aggregates; Risk Tides sparkline (TIDE-05) queries them | Say it while scrubbing the timeline |
| **Vultr** (MLH) | Hosts the FastAPI backend and static frontend (Caddy + systemd) | Backend URL on Vultr | Architecture slide |
| **.Tech domain** (MLH) | App served at pathpulse.tech | Domain live before video recording | Demo URL |
| **Notability** | Team planning notes, pitch rehearsal transcription, judge Q&A flashcards | ≥ 2 screenshots + note on Devpost; "Notability" tag | Devpost only |
| **Create-X** | Startup interest | Tick interest box at submission | — |
| **Auth0** (optional) | Saved places (ACCT-02) | Only if P0/P1 complete by Saturday 10 PM; never in demo path | Brief mention |

**Not targeted:** Visa, Impiricus, Meta, NSA challenges, SpaceXAI (we use Groq, not xAI Grok), DigitalOcean (not an MLH prize at HackGT 13), MongoDB (Tiger Data is the database).

**Prior-art differentiation:** SafeWay (HackGT 11) routed on hand-weighted crime/lighting factors; lumos.ai scores crime at city level. PathPulse forecasts *traffic* risk from real crash outcomes with pedestrian exposure, validates on a future holdout against the City's own High Injury Network, and explains every score.

### 8.1 Devpost submission checklist

Public repo with README (setup, architecture diagram, model card); 2–3 minute video that opens with the product name and the "wow" moment in the first 30 s; write-up sections: Inspiration, What it does, How we built it (name every sponsor tech and its job), Challenges, Accomplishments, What we learned, What's next; track = Oracle of the Deep; sponsor challenges ticked only where requirements are met; submit on Devpost and then at the HexLabs expo site with the Devpost link.

## 9. Scope, risks, and open questions

### 9.1 Scope tiers

**MVP (must ship by Sunday 4 AM feature freeze):** all P0 requirements — risk map, Risk Tides (hour + dry/wet), conditions with fallback, search, fastest vs PathPulse routes with detour budget, segment detail with SHAP and grounded Grok explanation, trust/about, demo mode.

**Polish (P1, Saturday evening onward):** City Pulse citywide hex layer and area card (CITY-01…04), voice "Listen" and Preview walk, day-of-week tides, sparkline, avoided-hotspot callouts, streaming explanations, theme by daylight, long-press pins.

**Stretch (P2):** Auth0 saved places, Balanced third route, live GPS Walk mode on a real phone.

**Future (post-hackathon):** cycling and wheelchair profiles, exposure-normalized risk using pedestrian counts, street-lighting data, crowdsourced near-miss reports, city/campus analyst dashboard, expansion beyond Atlanta.

### 9.2 Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| GDOT data access slower or messier than expected | Medium | High | Pull and snapshot data Friday night first; keep a cleaned Parquet snapshot in the repo; fall back to a smaller date range |
| Too few pedestrian crashes per segment to learn from | High | Medium | Model all crashes with pedestrian involvement as a feature/weight; hierarchical smoothing to corridor level; Limited-data badge |
| Exposure bias: busy streets look risky because more people walk there | High | Medium | State it in the model card; include road class and intersection density as structural proxies; frame scores as historical traffic risk, not per-person probability |
| Routing too slow on the full graph | Low | High | Restrict to coverage polygon; precompute edge weights per hour × condition; A\* with haversine heuristic |
| Venue Wi-Fi failure during Expo | Medium | High | Demo mode from cache; phone hotspot; recorded video as last resort |
| LLM produces a misleading sentence in front of judges | Low | High | Validator + template fallback; pre-warm demo explanations in cache |
| Scope creep | High | High | P0 list is the contract; anything else needs a teammate to finish their P0 first |

### 9.3 Open questions

| # | Question | Owner | Decide by |
| --- | --- | --- | --- |
| Q1 | Exact coverage polygon (Midtown + GT + Downtown vs. GT + Midtown only) based on graph size and data density | Data/ML | **Resolved (expanded Fri 11:50 PM):** the whole City of Atlanta boundary — 49,915 road segments, 84,758 walk nodes; routing p95 ~130 ms via a per-trip search box |
| Q2 | Which GDOT endpoint and date range give the cleanest pedestrian fields | Data/ML | **Resolved:** GEARS needs an agreement; use public ARC / City of Atlanta / CAP ArcGIS layers (timed crashes 2017–2025, year-only 2019–2024) plus StreetLight pedestrian activity and 2023 AADT |
| Q3 | ~~Grok model id~~ LLM provider | GenAI | **Resolved:** Groq `openai/gpt-oss-120b` → `gpt-oss-20b` → Gemini `gemini-3.8-flash` → template; voice via ElevenLabs |
| Q4 | Which MLH prizes are live this weekend | Any | **Resolved:** Tiger Data, ElevenLabs, Vultr, .tech, MongoDB, Solana, backboard.io; Gemini listed on MLH page — confirm at table |
| Q5 | Is voice (P1) in the 3-minute demo, or shown only in the video? | Pitch lead | Sat 8 PM |
