# PathPro: Devpost submission (paste-ready)

Each section below is one field of the Devpost form, in the order Devpost asks for it. `docs/devpost.md` is the long draft this is condensed from; every number here comes from `docs/metrics.json` or the model card.

**Before you paste:**
- [ ] Grok and Gemini are deployed and verified live on pathpro.tech. If not, delete the "Grok" and "Gemini" lines marked ⚑ first.
- [ ] Demo video uploaded to YouTube (unlisted is fine) with `media/pathpro_demo_v2.srt` attached.
- [ ] All four teammates have accepted the Devpost team invite.

---

## 1. Project name

PathPro

## 2. Elevator pitch (≤ 200 characters)

Lower-risk walk & ride routes for Atlanta, from a crash model that beats the City's own High Injury Network (74% vs 54%), plus Grok previews of the street fixes cities could build.

## 3. Thumbnail

`media/thumbnail_v2.png` (1280×720; Devpost crops thumbnails to 3:2, so check that the title stays visible in the preview).

## 4. About the project (paste as Markdown)

```markdown
## Inspiration

Many of us walk between Klaus, Tech Square, and Midtown MARTA late at night. Our friends, especially women, already plan routes around well-lit, busier streets and text each other when they get home. Yet every map app answers only one question: *what's fastest?*

Atlanta's pedestrian deaths concentrate on a small share of streets, and that risk rises and falls with the hour and the weather. We wanted a map that shows **where and when** traffic risk is highest, a route that trades a few minutes for much less exposure, and a way for cities to see which fixes matter most.

## What it does

**Two taps to a lower-risk route.** Open pathpro.tech (no install, no login), tap *Where to?*, pick a place. GPS fills in your start. The route card reads like a map app's:

> **23 min · 54% less traffic risk · +4 min vs fastest · arrive 10:52 PM**

- **Walk · Bike · E-bike · Scooter.** Georgia Tech → Inman Park by bike at 9 PM: **72% less traffic risk for +4 min**. Long walks get a MARTA hand-off. We deliberately don't route cars, because risk-aware car routing pushes traffic onto the streets people walk.
- **Walking navigation with voice callouts:** "High traffic risk ahead · 10th St NW in 120 m", so your eyes stay on the street.
- **"Why?" on every street:** factor bars that add up exactly to the score, crash history by hour, and a plain-language explanation you can listen to.
- **Risk Tides:** traffic risk hour by hour, dry or wet, weekday or weekend, for ~50,000 streets across the City of Atlanta.
- **Imagine this street redesigned** ⚑: for planners, Grok Imagine draws evidence-based fixes for that exact street, and Gemini checks the picture before it's shown.
- **Walking alone at night:** a *Well-lit & busier* route option, help points (100 Georgia Tech blue-light phones, police, fire, hospitals, MARTA), **Share my walk** with a friend, and an "Everything OK?" check-in with 911 one tap away.
- **Learns your routine on your phone only.** "Heading back to Klaus?" is offered after a couple of walks. History never leaves the device.
- **Community street reports** (blocked sidewalk, signal out, flooding…) show for 14 days.
- **Works offline** (`?demo=1`) for the expo Wi-Fi.

## Does it work? We tested on a year the model never saw

Trained on 2020–23, tested on 543 pedestrian crashes from 2024:

- The 10% of street length PathPro ranks highest held **74.3%** of them (95% spatial-block CI 70.5–78.3%).
- The City's **High Injury Network** got **53.8%**, past crashes 49.8%, and random 11.9%. ROC-AUC is 0.89.
- **Ride model:** 69.9% of 2024 cyclist crashes (CI 64.0–76.1%) vs 43.6% for the High Injury Network.

**What that buys:** the same budget spent on 10% of street length reaches **~38% more** of next year's pedestrian crashes than the High Injury Network, and ~60% more bike crashes. For a person: **+4 minutes, 54% less exposure**.

## How we built it

- **Data:** ~250k public crash records from 8 ArcGIS layers (ARC, City of Atlanta, Central Atlanta Progress, Georgia Tech), deduplicated, stripped of personal fields, and snapped to OpenStreetMap streets. We caught one source storing local time as UTC by checking it against its light condition (agreement went from 60% to 94%).
- **Model:** an exposure-aware safety performance function (Poisson GLM + monotone LightGBM, spatial-block CV) blended with each street's history by Empirical Bayes, plus a temporal GLM for hour, day, darkness, and rain. Features: pedestrian activity, traffic volume, speed, lanes, transit, sidewalks, signals, crossings. **No demographic or income features.**
- **Grok (xAI)** ⚑: Grok writes each "Why?" explanation from the street's own evidence; a validator rejects any sentence with a number that isn't in the evidence, so the score always comes from the model. **Grok Voice** speaks navigation callouts. **Grok Imagine** renders street redesigns from a prompt the server builds from the street's real risk factors, labeled "AI illustration … not a real photo".
- **Gemini** ⚑: multimodal review of every Grok Imagine picture. It confirms which planned fixes appear ("Checked by Gemini: shows 3 of 4 planned fixes") and rejects images with readable text, logos, or identifiable faces. Gemini is also in the explanation fallback chain.
- **Engine-out design:** explanations fall back Grok → Groq → Gemini → template; voice falls back Grok Voice → ElevenLabs → device. The offline demo needs no network at all.
- **Vultr:** the whole app runs on one Vultr VM in Atlanta (Caddy auto-HTTPS, hardened systemd, firewall), deployed with one command.
- **.tech:** **pathpro.tech**. Say it out loud: *path protect*.
- **Tiger Data** (TimescaleDB + PostGIS): 220,594 crash rows in a hypertable, a continuous aggregate behind each street's "when crashes happened here" chart, PostGIS geometry, and a 9.6M-row risk grid.
- **MongoDB Atlas:** community reports (2dsphere viewport query, 14-day TTL, atomic upserts that turn repeats into confirmations) and Share my walk (6-hour TTL, hashed owner tokens).
- **ElevenLabs:** the "Sarah" voice for spoken explanations and alerts, and the automatic fallback when Grok Voice is unavailable.
- **App:** React + TypeScript + MapLibre + deck.gl, FastAPI, SciPy Dijkstra routing (~150 ms median for both route plans).
- **Engineering:** test-first throughout, with independent code, ML, and security reviews. About 1,145 automated tests (237 data, 337 API, 552 web, 19 end-to-end).

## Safety context, without stigma

Crime maps are known to label whole neighborhoods. So:
- Atlanta Police **crimes against persons** are shown for context only: grouped into hexes by time of day, with no addresses or victim details, and always beside a fairness note.
- Bands use an exposure-normalized Empirical-Bayes rate, so an area with no reports is never marked "higher".
- **Crime is never used to route.** A test multiplies crime counts by 1,000 and the routes don't change.
- Lighting is known for only ~4% of streets; unknown stays unknown, never "dark".

## Challenges we ran into

- **A third of crashes wouldn't snap** because Midtown sidewalks are mapped separately from roads. Modeling on road centerlines and letting sidewalks inherit the risk took the snap rate from 66% to 96%.
- **A mentor told us our first UI "isn't intuitive."** We rebuilt it that afternoon: map-first, GPS by default, a route sheet like Google Maps, walking navigation, and learned routines.
- **Every other street was drawn backwards** (OSMnx stores many geometries reversed), so routes zigzagged and navigation overstated distance 1.6×. We fixed it and added a regression test.
- **Honest statistics:** our reviewer caught confidence intervals that were too narrow, so we now resample spatial blocks. It also found that rain adds little, and we report that.

## Accomplishments we're proud of

- The model beats the City of Atlanta's own High Injury Network on future crashes, with confidence intervals.
- Every number on screen traces to the model. The AI can't invent one.
- The safety layer is useful and honest about its limits, and it never routes around neighborhoods.
- It keeps working when the weather API, an LLM, a database, GPS, or the Wi-Fi fails.

## What we learned

Most of the work is data plumbing and honest evaluation, not model choice. Exposure bias is real in both crash and crime data, and saying so makes the claims stronger. Watching one real person use the app on a phone taught us more than any test.

## What's next for PathPro

Wheelchair and stroller profiles, citywide lighting data with the City or Georgia Power, a Vision Zero planning dashboard with Grok Imagine redesigns for the top-ranked streets, and new cities by swapping one coverage polygon.
```

## 5. Built with (tags)

(Devpost allows 25) python, fastapi, react, typescript, maplibre, deck.gl, lightgbm, scikit-learn, statsmodels, osmnx, geopandas, grok, grok-imagine, grok-voice, xai, gemini, groq, elevenlabs, timescaledb, postgis, tiger-data, mongodb-atlas, vultr, playwright, cursor

## 6. "Try it out" links

- https://pathpro.tech
- https://pathpro.tech/?demo=1 (offline demo)
- https://github.com/ShaikNagurShareef/PathPro

## 7. Video demo link

The YouTube URL of `media/pathpro_demo_v2.mp4`, or v3 once it's recorded with Grok Voice.

## 8. Image gallery (upload in this order; the caption is the first line)

1. `docs/images/gallery/02-phone-route-comparison.png`: "Two taps to a lower-risk route: +4 min, 54% less traffic risk"
2. Grok Imagine redesign, a screenshot of the street sheet with the image and the "Checked by Gemini" line ⚑ (take it after the deploy)
3. `docs/images/gallery/03-phone-navigation-alert.png`: "Walking navigation with spoken high-traffic-risk callouts"
4. `docs/images/gallery/04-desktop-risk-tides-home.png`: "Risk Tides: traffic risk hour by hour across Atlanta"
5. `docs/images/gallery/05-desktop-route-explanation.png`: "Why? Factor bars that add up exactly, plus a grounded explanation"
6. `docs/images/gallery/06-personal-safety-fairness-help-points.png`: "Safety context with a fairness note, never used to route"
7. `docs/images/gallery/tiger-hourly.png`: "When crashes happened here, from a Tiger Data continuous aggregate"
8. `docs/images/gallery/08-share-my-walk-follow.png`: "Share my walk: a friend follows along live"
9. `docs/images/gallery/01-phone-home-routine-suggestion.png`: "Learns your routine, on your phone only"
10. `docs/images/gallery/07-city-pulse-area-score-live.png`: "City Pulse: area scores for all 3,537 hexes"

## 9. Submission form questions

- **Schools:** Georgia State University
- **General track (one):** Oracle of the Deep - ML/AI
- **Sponsor track 1:** Aramco - A Marina's Mission
- **Sponsor track 2:** SpaceXAI - Make it Legendary ⚑ (the form allows only two sponsor tracks; Notability's prize is "Best Use of Notability", which we don't use)
- **MLH prizes:** Best use of ElevenLabs, Gemini API ⚑ (Gemini project number 1091754630519), TigerData, Vultr, MongoDB Atlas. The .tech prize is entered through the domain question.
- **AI tools this weekend (shown in the gallery):** OpenAI (gpt-oss via Groq), Anthropic, Gemini, ElevenLabs, Other (xAI Grok, Cursor)
- **AI tools used:** AI coding assistants (Claude Code, Cursor) during development; Grok models, Grok Imagine, Grok Voice and Gemini in the product. We followed a test-first workflow with independent review; scope, product decisions (including the safety layer and its safeguards), and review were ours.
- **Domain (.tech):** pathpro.tech
- **Data credits:** crash data from ARC, the City of Atlanta, Central Atlanta Progress, and Georgia Tech open data; Atlanta Police open data; OpenStreetMap contributors. The full list is in the README and `docs/safety_sources.md`.

## 10. After submitting

- Paste the Devpost link at expo.hexlabs.org.
- Notability: attach `docs/process/process_notes.pdf` per the sponsor's instructions.
