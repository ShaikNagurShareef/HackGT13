# PathPro decision log

**Team CodingClaws, HackGT 13:** Nagur Shareef Shaik, Sahith Reddy Thummala, Pranav Nagothu, Geethanjali Nagaboina.

This log records what we decided while building PathPro, when, why, and what we chose not to do. Times are Eastern (EDT), September 25–26, 2026. The code history (`git log`) has the exact commits. For the full process story see [process/process_notes.md](process/process_notes.md).

## Contents
1. [Scope and principles](#1-scope-and-principles)
2. [Stack and sponsors](#2-stack-and-sponsors)
3. [Data and modeling](#3-data-and-modeling)
4. [Naming, domain, and repository](#4-naming-domain-and-repository)
5. [Hosting and deployment](#5-hosting-and-deployment)
6. [Product and UX](#6-product-and-ux)
7. [Personal safety and crime](#7-personal-safety-and-crime)
8. [Transport modes](#8-transport-modes)
9. [Security and privacy incidents](#9-security-and-privacy-incidents)
10. [Demo, video, and submission](#10-demo-video-and-submission)
11. [Things we deliberately did not do](#11-things-we-deliberately-did-not-do)

---

## 1. Scope and principles

| When | Decision | Why |
| --- | --- | --- |
| Fri evening | Build from our PRD (`Requirements (PRD).md`) using a test-first workflow: plan → failing test → implement → independent review → verify. | Hackathon speed without losing correctness; every feature lands with tests. |
| Fri evening | Use prior hackathon projects (e.g. lumos.ai) as **reference only**, never as code or design to match. | Originality; avoid copying another team's approach. |
| Fri evening | Core claim: **forecast pedestrian traffic risk from real crash outcomes with pedestrian exposure**, validated on a future year against the City's own High Injury Network. | A model judges can check is stronger than a hand-weighted score. |
| Fri evening | **Honest numbers only.** Every metric on screen comes from `docs/metrics.json` with confidence intervals; the LLM never produces a number. | Judges and users should be able to trust every figure. |
| Fri evening | Copy rules: say "traffic risk", "lower-risk"; never "safe", "safest", "dangerous area", "guaranteed". A validator enforces this on LLM output. | Risk can be reduced, not eliminated; avoid stigmatizing places. |
| Fri night | Expand coverage from a Midtown core to the **entire City of Atlanta** (49,915 street segments). | A citywide tool is far more useful and credible. |

## 2. Stack and sponsors

| When | Decision | Why |
| --- | --- | --- |
| Fri evening | Explanations: **Groq** (`openai/gpt-oss-120b`, then `gpt-oss-20b`) first, **Gemini** as fallback, then a deterministic template. | Sub-second answers with graceful fallback; the demo never depends on one provider. |
| Fri evening | **Tiger Data** (TimescaleDB + PostGIS) as system of record, never on the demo's hot path. | The crash hypertable and hourly continuous aggregate power "when crashes happened here". |
| Fri evening | **ElevenLabs** for voice, with the browser's built-in speech as fallback. | Eyes-up navigation alerts and Listen. |
| Fri evening | **Vultr** hosting and a **.tech** domain. | MLH sponsor prizes, and a real deployed app. |
| Sat morning | Add **MongoDB Atlas** "in the best way possible": community street reports, and later Share my walk. | Geo queries, TTL expiry, and atomic upserts fit user-generated, expiring data. |
| Sat morning | Keep **Geoapify** for address search, with a local gazetteer as fallback. | Search that works for any Atlanta address. |

## 3. Data and modeling

| When | Decision | Why |
| --- | --- | --- |
| Fri night | Model unit: OSM road segments; sidewalks inherit risk from the nearest road. | Most Midtown sidewalks are mapped separately, so snapping to the walk graph lost a third of crashes (snap rate 66% → 96%). |
| Fri night | Spatial model: Poisson GLM + monotone LightGBM ensemble, spatial-block CV, Empirical Bayes; temporal Poisson GLM for hour, day, darkness, and rain. | Accuracy while staying explainable; factor bars add up exactly to each score. |
| Fri night | **No demographic or income features**, ever. | Fairness; avoid encoding bias. |
| Sat | Result: the top 10% of street length held **74.3%** [70.5–78.3] of 2024 pedestrian crashes, against 53.8% for the City's High Injury Network, 49.8% for past crashes, and 11.9% for a random ranking. | Report the measured baseline, not the theoretical one. |
| Sat 04:10 | Fix the LLM validator: numbers inside evidence text (e.g. "2020–2024") count as grounded. Raise the explanation time budget to 4 s. | Groq's correct paraphrases were being rejected, and Gemini needed time to answer. |

## 4. Naming, domain, and repository

| When | Decision | Why |
| --- | --- | --- |
| Fri evening | Working name **PathPulse**. | A name with meaning for walking and time-varying risk. |
| Sat 10:50 | Rename the repository to **PathPro**. | The team's preference. |
| Sat | Domain **pathpro.tech**, read as "path protect". | An MLH coach said the .tech prize favors puns. We also considered `walkpro.tech` and `pathde.tech` ("path detect"). |
| Sat afternoon | Rename the product from PathPulse to **PathPro** in all user-facing text. Internal identifiers (Python packages, server paths, database names) keep `pathpulse`. | One brand for users. Renaming infrastructure would add migration risk with no user benefit. |
| Sat evening | Tagline: **"See the risks on your way, before you go."** It replaces "See traffic risk before you walk into it." | Team feedback: "Not just traffic." PathPro shows several kinds of risk and supports riding. |

## 5. Hosting and deployment

| When | Decision | Why |
| --- | --- | --- |
| Fri night | Interim hosting: a static demo on GitHub Pages plus the live API through a Cloudflare tunnel from a laptop. | Something working and shareable before cloud accounts were ready. |
| Sat | **Retire GitHub Pages; host only on Vultr.** | Team decision: the app should live on Vultr. |
| Sat 11:15 | One Vultr VM in Atlanta (Ubuntu 24.04, 2 GB) with Caddy (automatic HTTPS), a hardened systemd service, and ufw. MLH credits applied. | Low latency for Atlanta users, and one command to deploy. |
| Sat 11:20 | Serve on `155-138-233-35.sslip.io` alongside the domain. | Real HTTPS before DNS was ready. |
| Sat 11:25 | Set `HOME` outside `/home` in the systemd unit. Build the Python environment on the system interpreter. | The unit's `ProtectHome=true` hardening blocked the database client's certificate lookup and a Python install under `/home`. |
| Sat afternoon | Deploy from a **clean git worktree** of a green commit, copying the real bundle directory. | Agents were editing the main tree, and `rsync` would have shipped a symlink instead of the data. |

## 6. Product and UX

| When | Decision | Why |
| --- | --- | --- |
| Sat 11:30 | **Mentor feedback:** "UI/UX is not intuitive", "GPS would be a must-have… and suggest based on that", with a car that learned the mentor's routine as the example. | Real user reaction on a phone. |
| Sat afternoon | Rebuild mobile-first: a map-first home with one "Where to?" box, **GPS start ("Your location")**, a Google-Maps-style route sheet with a big **Start**, and **walking navigation** with spoken alerts. | Two taps from opening the app to a route. |
| Sat afternoon | **Learned routines on the device only** ("Heading back to Klaus?"). Nothing is sent to the server; there is a Clear history button. | The mentor's idea, with privacy as a feature. |
| Sat afternoon | A proper **desktop layout** (≥1024 px): a persistent sidebar, and Risk Tides docked on the map. | Team feedback: the web view looked like a phone screen. |
| Sat | Share my walk survives a page reload through a per-tab session and a "Resume sharing?" prompt. | A friend's live link shouldn't silently freeze. |

## 7. Personal safety and crime

| When | Decision | Why |
| --- | --- | --- |
| Fri evening | Original scope: **traffic risk only, no crime data.** | Crime maps are known to stigmatize neighborhoods. |
| Sat 13:08 | Team decision to **add personal safety**. Of three options (signals only; signals + a crime layer; full crime-aware routing), we chose **signals + an informational Atlanta Police crime layer**. | Users, especially people walking alone at night, want this context. Full crime-aware routing was rejected as the highest bias risk. |
| Sat | Safeguards: crimes against persons only; no addresses or victim fields; aggregated to H3 hexes by time of day; bands from an exposure-normalized Empirical-Bayes posterior (an area with no reports is never "higher"); always shown with a fairness note; **crime never enters routing** (a test multiplies crime counts by 1,000 and routes don't change). | Useful context without steering people away from neighborhoods. |
| Sat | Safety signals may shape routing only through the optional "Well-lit & busier (after dark)" preference. Unknown lighting stays unknown, never "dark". | Lighting data covers about 4% of streets; we don't guess. |
| Sat | Tools: **Share my walk** (a live link, 6-hour TTL, hashed owner token) and a **late check-in** ("Everything OK?", Call 911). | Practical support for walking alone. |

## 8. Transport modes

| When | Decision | Why |
| --- | --- | --- |
| Sat 14:20 | Team feedback: "Just walking for long distances is unrealistic; it can be driving, cycling, e-bike." | Real trips across Atlanta are longer than a walk. |
| Sat 14:25 | Add **Bike, E-bike, and Scooter** with a validated ride model, plus a **MARTA hand-off** for long walks. **No driving routes.** | Cyclists and scooter riders are vulnerable road users like pedestrians. Risk-aware car routing pushes traffic onto the neighborhood streets where people walk, and that space is crowded. |
| Sat 14:25 | Hard cut-off: ship walk-only if the ride model missed its targets by 01:30. | Protect the submission. |
| Sat 15:00 | The first cyclist-only model (57.4%) lost to simply reusing the walk model. We chose the training label on the 2023 validation year: pooled pedestrian + cyclist crashes, scored on cyclist crashes only. Final: **69.9%** [64.0–76.1] vs 43.6% HIN, 30.4% past bike crashes, 12.0% random. | Honest model selection. We claim ranking, not calibrated cyclist counts. |

## 9. Security and privacy incidents

| When | What happened | What we did |
| --- | --- | --- |
| Sat | Automation that read keys from the browser had a masking bug. A newly created cloud API key appeared in a log. | Fixed the masking (decoded JSON strings are masked before printing). The exposed key was flagged for deletion, and a separate key was created for deployment. |
| Sat | Review: shared-walk position updates could reach the database even when throttled. | Added an in-memory per-walk gate before any database read. Kept these updates off the shared paid rate limit, because the expo venue shares one internet address. |
| Sat | Review: a partial safety-data download could crash the bundle build. | The build now skips the optional layer with a warning. |
| Throughout | Secrets live only in `backend/.env` (never in git or the frontend). A pre-commit secret scan runs on every commit. | — |

## 10. Demo, video, and submission

| When | Decision | Why |
| --- | --- | --- |
| Sat | Keep an **offline demo** (`?demo=1`) with recorded responses for walking, riding, safety, and MARTA. | The expo Wi-Fi may fail. |
| Sat | Demo video v2 (about 6 min): the CodingClaws intro; motivation (late-night walks, and friends, especially women, planning around well-lit, busier streets); how PathPro differs from existing apps; usability; the risks PathPro shows (traffic, reported crimes against persons, lighting, weather, hazards); who it's for; results and ROI; one scene per sponsor; ElevenLabs narration, burned-in captions plus SRT/VTT, and a soft music bed. | The team's request: 3–5 minutes, slightly over allowed. |
| Sat | ROI framing from our own holdout numbers: the same budget on 10% of streets reaches about 38% more pedestrian crashes (and about 60% more cyclist crashes) than the High Injury Network. The one national figure (NHTSA's $340 billion economic cost) is cited from its primary source. | Impact claims we can defend. |
| Sat | Keep "we" throughout. PathPro is a team project; AI tools are disclosed on Devpost. | Accurate attribution. |

## 11. Things we deliberately did not do

- **No car routing**, for the reasons in section 8.
- **No crime-aware routing.** Crime is information, never a routing input.
- **No demographic or income features** anywhere.
- **No login.** Routines stay on the device, and shared walks expire.
- **No guessing** where data is missing: unknown lighting and unmeasured scooter crashes are labeled as such.
- **No invented numbers.** The LLM cannot introduce a number that isn't in the evidence.
