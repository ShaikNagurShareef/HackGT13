# PathPro decision log

**HackGT 13, solo build:** Nagur Shareef Shaik (team name Coding Claws, Georgia State University).

This log records what I decided while building PathPro, when, why, and what I chose not to do. Times are Eastern (EDT), September 25–26, 2026. The code history (`git log`) has the exact commits. For the full process story see [process/process_notes.md](process/process_notes.md).

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
11. [Things I deliberately did not do](#11-things-i-deliberately-did-not-do)

---

## 1. Scope and principles

| When | Decision | Why |
| --- | --- | --- |
| Fri evening | Build from my PRD (`Requirements (PRD).md`) using a test-first workflow: plan → failing test → implement → independent review → verify. | Hackathon speed without losing correctness; every feature lands with tests. |
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
| Sat 19:30 | **Grok first** in the explanation chain (Grok → Groq → Gemini → template), all under the same validator. **Grok Voice** first for Listen and navigation callouts, with ElevenLabs and then the device voice as backups. | SpaceXAI "Make it Legendary" track; engine-out redundancy means no single provider can take explanations or voice down. |
| Sat 19:30 | **"Imagine this street redesigned"** with Grok Imagine. The server builds the prompt from the street's modeled risk factors and road class only (never user text, never street names), and every image carries "AI illustration of evidence-based street fixes by Grok Imagine — not a real photo". Images are cached per street; new ones are capped per day overall and per visitor. | A planner can see an evidence-based fix before spending on concrete. The picture never changes a score. |
| Sat 20:06 | **Grok draws, Gemini checks.** Gemini reviews each illustration against the server's list of planned fixes before it is cached or shown, and rejects images with readable text, logos, or identifiable faces (one retry, then a friendly message). Its JSON answer is parsed strictly; if Gemini is unreachable the image is shown without the check line. | An image model can draw signage, brands, or people that were never asked for. A second model with a narrow, strictly parsed job catches that. |
| Sat 20:10 | The image check uses its own Gemini model setting, defaulting to `gemini-3.1-flash-lite`. | Verified live; the model tried first was returning errors, and a separate setting keeps per-model free-tier quotas apart. |
| Sat 21:09 | **Ask PathPro on Backboard (v1):** a Backboard assistant answers questions about how PathPro works, only from PathPro's curated docs. Public questions use read-only memory. Every answer is validated (banned words, crime framing, links, topicality, every number must appear in the docs); anything that fails becomes a fixed pointer to the model card. | Judges and users ask "how do you know?"; the answer should come from the model card, not from an LLM's imagination. |
| Sat 21:21 | Ask limits: 20 questions per visitor per day, checked before a shared daily budget. Thread tokens are signed by the server and bound to their assistant. | The expo shares one internet address, and a forged thread id must never reach Backboard. |
| Sat 21:46 | **Ask PathPro v2:** "Ask about this street / route / area" sends server-built evidence (never coordinates or free text from the map) with the question, plus live conditions; answers cite their source docs. | Answers about what's on screen, grounded in the same evidence the explanations use. |
| Sat 21:52 | **Opt-in private memory** ("Remember my preferences", off by default): turning it on clones the docs assistant into a private one for that browser; "Forget me" deletes the clone and everything it remembered. The clone keeps only stated travel preferences, never places, streets, or routes. | Useful memory without a shared store anyone can write to, and without location history. |
| Sat 22:00 | Memory is written only from plain questions; a question carrying street, route, or area context can read memory but never writes it. Street names (from OpenStreetMap, which anyone can edit) are flattened to one short line before they reach any LLM. | Context questions would otherwise leak places into memory, and a crafted street name could try to instruct the model. |

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
| Sat 10:50 | Rename the repository to **PathPro**. | My preference. |
| Sat | Domain **pathpro.tech**, read as "path protect". | An MLH coach said the .tech prize favors puns. I also considered `walkpro.tech` and `pathde.tech` ("path detect"). |
| Sat afternoon | Rename the product from PathPulse to **PathPro** in all user-facing text. Internal identifiers (Python packages, server paths, database names) keep `pathpulse`. | One brand for users. Renaming infrastructure would add migration risk with no user benefit. |
| Sat evening | Tagline: **"See the risks on your way, before you go."** It replaces "See traffic risk before you walk into it." | Feedback: "Not just traffic." PathPro shows several kinds of risk and supports riding. |

## 5. Hosting and deployment

| When | Decision | Why |
| --- | --- | --- |
| Fri night | Interim hosting: a static demo on GitHub Pages plus the live API through a Cloudflare tunnel from a laptop. | Something working and shareable before cloud accounts were ready. |
| Sat | **Retire GitHub Pages; host only on Vultr.** | My decision: the app should live on Vultr. |
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
| Sat afternoon | A proper **desktop layout** (≥1024 px): a persistent sidebar, and Risk Tides docked on the map. | Feedback: the web view looked like a phone screen. |
| Sat | Share my walk survives a page reload through a per-tab session and a "Resume sharing?" prompt. | A friend's live link shouldn't silently freeze. |

## 7. Personal safety and crime

| When | Decision | Why |
| --- | --- | --- |
| Fri evening | Original scope: **traffic risk only, no crime data.** | Crime maps are known to stigmatize neighborhoods. |
| Sat 13:08 | Decision to **add personal safety**. Of three options (signals only; signals + a crime layer; full crime-aware routing), I chose **signals + an informational Atlanta Police crime layer**. | Users, especially people walking alone at night, want this context. Full crime-aware routing was rejected as the highest bias risk. |
| Sat | Safeguards: crimes against persons only; no addresses or victim fields; aggregated to H3 hexes by time of day; bands from an exposure-normalized Empirical-Bayes posterior (an area with no reports is never "higher"); always shown with a fairness note; **crime never enters routing** (a test multiplies crime counts by 1,000 and routes don't change). | Useful context without steering people away from neighborhoods. |
| Sat | Safety signals may shape routing only through the optional "Well-lit & busier (after dark)" preference. Unknown lighting stays unknown, never "dark". | Lighting data covers about 4% of streets; PathPro doesn't guess. |
| Sat | Tools: **Share my walk** (a live link, 6-hour TTL, hashed owner token) and a **late check-in** ("Everything OK?", Call 911). | Practical support for walking alone. |

## 8. Transport modes

| When | Decision | Why |
| --- | --- | --- |
| Sat 14:20 | Feedback: "Just walking for long distances is unrealistic; it can be driving, cycling, e-bike." | Real trips across Atlanta are longer than a walk. |
| Sat 14:25 | Add **Bike, E-bike, and Scooter** with a validated ride model, plus a **MARTA hand-off** for long walks. **No driving routes.** | Cyclists and scooter riders are vulnerable road users like pedestrians. Risk-aware car routing pushes traffic onto the neighborhood streets where people walk, and that space is crowded. |
| Sat 14:25 | Hard cut-off: ship walk-only if the ride model missed its targets by 01:30. | Protect the submission. |
| Sat 15:00 | The first cyclist-only model (57.4%) lost to simply reusing the walk model. I chose the training label on the 2023 validation year: pooled pedestrian + cyclist crashes, scored on cyclist crashes only. Final: **69.9%** [64.0–76.1] vs 43.6% HIN, 30.4% past bike crashes, 12.0% random. | Honest model selection. PathPro claims ranking, not calibrated cyclist counts. |

## 9. Security and privacy incidents

| When | What happened | What I did |
| --- | --- | --- |
| Sat | Automation that read keys from the browser had a masking bug. A newly created cloud API key appeared in a log. | Fixed the masking (decoded JSON strings are masked before printing). The exposed key was flagged for deletion, and a separate key was created for deployment. |
| Sat | Review: shared-walk position updates could reach the database even when throttled. | Added an in-memory per-walk gate before any database read. Kept these updates off the shared paid rate limit, because the expo venue shares one internet address. |
| Sat | Review: a partial safety-data download could crash the bundle build. | The build now skips the optional layer with a warning. |
| Sat 19:39 | Security review of the Grok work: provider objects could print API keys in their debug representation; Imagine had only a global daily cap; TTS audio lacked `nosniff`. | Keys hidden from provider representations, a per-visitor daily cap on Imagine, and `X-Content-Type-Options: nosniff` on audio. |
| Sat 19:58 | The hardened systemd unit (`ProtectSystem=strict`) blocked the Imagine image cache. | A dedicated writable cache directory in the unit. |
| Sat 21:21 | Security review of Ask PathPro v1: raw thread ids from the browser, no per-visitor cap, answers could carry arbitrary links. | Signed, assistant-bound thread tokens; a per-visitor daily cap; links allowed only to PathPro's own corpus files; an on-topic check. |
| Sat 22:00 | Review of Ask v2 memory: context questions could have written places into memory; street names reached LLMs unflattened. | Fixed as in section 2, with regression tests. |
| Throughout | Secrets live only in `backend/.env` (never in git or the frontend). A pre-commit secret scan runs on every commit. | — |

## 10. Demo, video, and submission

| When | Decision | Why |
| --- | --- | --- |
| Sat | Keep an **offline demo** (`?demo=1`) with recorded responses for walking, riding, safety, and MARTA. | The expo Wi-Fi may fail. |
| Sat | Demo video v2 (about 6 min): a team intro (since found to be outdated, see the correction below); motivation (late-night walks, and friends, especially women, planning around well-lit, busier streets); how PathPro differs from existing apps; usability; the risks PathPro shows (traffic, reported crimes against persons, lighting, weather, hazards); who it's for; results and ROI; one scene per sponsor; ElevenLabs narration, burned-in captions plus SRT/VTT, and a soft music bed. | Target: 3–5 minutes, slightly over allowed. |
| Sat | ROI framing from PathPro's own holdout numbers: the same budget on 10% of streets reaches about 38% more pedestrian crashes (and about 60% more cyclist crashes) than the High Injury Network. The one national figure (NHTSA's $340 billion economic cost) is cited from its primary source. | Impact claims that hold up. |
| Sat | Narrative voice "we", based on a four-person team framing. | Superseded: the framing was wrong (see the correction row below). |
| Sat 20:38 | Devpost form: general track Oracle of the Deep; sponsor tracks Aramco "A Marina's Mission" (first) and SpaceXAI "Make it Legendary" (second); MLH prizes ElevenLabs, Gemini API, TigerData, Vultr, MongoDB Atlas; school Georgia State University; domain pathpro.tech. Backboard is ticked only after Ask PathPro is deployed. | The form allows two sponsor tracks. Nothing is claimed live before it is live. |
| 2026-09-26 (Sat, late evening) | **Record corrected: PathPro is a solo build** by Nagur Shareef Shaik under the team name Coding Claws. Earlier docs and the v2 video listed a four-person team, which was wrong. The docs now use first person singular, and the v2 video's team cards are marked outdated pending a v3 re-cut. | Accurate attribution. AI tools are disclosed in one line on Devpost. |

## 11. Things I deliberately did not do

- **No car routing**, for the reasons in section 8.
- **No crime-aware routing.** Crime is information, never a routing input.
- **No demographic or income features** anywhere.
- **No login.** Routines stay on the device, and shared walks expire.
- **No guessing** where data is missing: unknown lighting and unmeasured scooter crashes are labeled as such.
- **No invented numbers.** The LLM cannot introduce a number that isn't in the evidence.
- **No public writes to shared memory.** Ask PathPro's shared assistant is read-only for visitors; memory exists only in a visitor's own opt-in clone, and "Forget me" deletes it.
- **No real-looking street photos.** Every Grok Imagine image is labeled as an AI illustration, not a real photo.
