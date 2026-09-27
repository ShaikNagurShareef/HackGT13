# Sponsor and prize checklist

Status as of Sat Sep 26, 2026, 7:00 AM ET. Submit on Devpost by **Sun 07:30** (hacking ends 08:00), then add the link at expo.hexlabs.org. Expo: Sun 09:30–11:00, Klaus Atrium.

`[x]` done and verified live · `[ ]` still to do

## MLH sponsor prizes

### Tiger Data: Best Use of Tiger Data
- [x] Free Tiger service `pathpulse` (Shared tier, AWS us-east-1); `DATABASE_URL` in `backend/.env`
- [x] Schema: `crashes` hypertable, `crashes_hourly` continuous aggregate, PostGIS geometry, versioned `risk_grid` (`data/sql/schema.sql`)
- [x] Loaded: 49,915 street segments, 220,594 crash rows, 9,583,680 risk-grid rows
- [x] Live in the app: `GET /api/segments/{id}/hourly` powers "when crashes happened here" on every street sheet
- [ ] Screenshot of the Tiger console (service + hypertable) for the Devpost gallery
- [ ] Show the hourly chart in the demo video

### Vultr: Best Use of Vultr
- [x] $100 MLH gift code applied (credit expires Oct 27, 2026); API access enabled; `VULTR_API_KEY` in `backend/.env`
- [x] VM `pathpulse`: Atlanta (`atl`), Ubuntu 24.04, 1 vCPU / 2 GB, IP 155.138.233.35
- [x] Caddy (automatic HTTPS, security headers) + hardened systemd unit + ufw; deployed with `deploy/go.sh`
- [x] Live and verified end to end at https://pathpro.tech (also https://155-138-233-35.sslip.io): routes, Groq explanations, ElevenLabs audio, Geoapify search, Tiger hourly history, MongoDB reports
- [x] Laptop tunnel retired; Vultr is the only host
- [ ] Delete the leaked "Default" API key in Vultr → Account → API (the deploy uses the `pathpro-deploy` key)

### .tech domains: Best .tech Domain
- [x] .tech promo code claimed on MLH (free for 1 year; **expires Mon Sep 28, 8 PM ET**; redeem at get.tech)
- [x] Registered **pathpro.tech** ("path protect", a pun as the MLH coach asked) with the MLH .tech code, valid until Sep 26, 2027
- [ ] **Verify the registrant email** (get.tech dashboard → "Resend Email"), or the registrar can deactivate the domain
- [x] A records `@` and `www` → 155.138.233.35; Caddy issued Let's Encrypt certificates for both
- [x] https://pathpro.tech loads the app (map, tiles, live API) in the browser

### ElevenLabs: Best Use of ElevenLabs
- [x] Free-tier key, restricted to text-to-speech, voices (read), models and user
- [x] Voice "Sarah" (reassuring, calm), `ELEVENLABS_VOICE_ID` set
- [x] Live: `POST /api/tts` returns MP3 for "Listen" and walk alerts; it speaks only server-written text
- [ ] Show "Listen" with audio on in the demo video

### Gemini API: Best Use of Gemini API
- [x] Key saved (free tier, "HackGT" key in AI Studio) and verified
- [x] Second provider in the explanation chain (Groq → Gemini → template), under the same validator
- [x] "Grok draws, Gemini checks": Gemini (multimodal, structured JSON output) reviews every Grok Imagine illustration before it is cached or shown. It confirms which planned fixes appear ("Checked by Gemini: shows N of M planned fixes") and rejects images with readable text, logos, or identifiable faces (one retry, then a friendly error). Tests mock all Gemini and xAI calls
- [ ] Confirm at the MLH table that this prize is offered at HackGT 13 (it's on the MLH page but not on Devpost)

## HackGT tracks and other sponsors

### SpaceXAI "Make it Legendary" (Grok, Grok Imagine, Grok Voice; built with Cursor)
Pitch: *mission control for every walk home*. We align with SpaceX's engineering culture (first principles, test like you fly, engine-out redundancy, reusability, public-health mission), not its branding. No logos, and no suggestion of a partnership.
- [ ] xAI account (shaiknagurshareef6@gmail.com), API key in `backend/.env` as `XAI_API_KEY`, $25 credits from the SpaceXAI promo code on the sponsor slide (Grok Voice + Imagine; code kept out of git)
- [ ] Cursor account (same email), 1 month of Pro from the SpaceXAI event redeem link; do part of the Grok work in Cursor so "built with Cursor" is true
- [ ] Grok explanations (Grok → Groq → Gemini → template), Grok Voice alerts, and "Imagine this street redesigned" (Grok Imagine) live on pathpro.tech
- [ ] Video v3: Grok Voice narration plus a 20 s "Make it Legendary" scene (script in `media/pathpro_demo_script.md`)
- [ ] Publish the "Make it Legendary" section in `docs/devpost.md` (it's gated on the live check) and select the track

### Oracle of the Deep (ML/AI + visualization)
- [x] Crash-trained model (GLM + LightGBM ensemble, Empirical Bayes) with spatial and temporal holdouts (`docs/model_card.md`)
- [x] Risk Tides: hourly and weather-aware map; factor bars add up exactly to each score
- [ ] Select the track on Devpost; put the headline metric in the first paragraph

### Aramco "A Marina's Mission" (social good)
- [x] Framing: pedestrian deaths as a public-health problem; traffic risk only, with no crime or demographic features
- [ ] Select the track on Devpost

### Notability "Trust the Process"
- [ ] Gather planning notes and screenshots (plan, milestones, model iterations) and submit per the sponsor's rules

### Create-X
- [ ] Tick the Create-X interest box on Devpost

### MongoDB Atlas: Best Use of MongoDB Atlas
- [x] Share my walk: `shared_walks` collection with a TTL index (6 h after last update), unique walk_id, hashed owner tokens, optimistic-concurrency updates; live on pathpro.tech
Job: community street reports. Tiger Data stays the system of record for crashes and scores; Atlas holds what walkers tell us, and it never feeds the model.
- [x] `ReportsRepository` on pymongo's async client with tight timeouts and a cooldown; unset or unreachable Atlas hides the feature and nothing else breaks
- [x] Indexes: 2dsphere on `loc`, TTL on `expires_at` (14 days after the last confirmation), unique `{seg_id, category}`; created at API startup
- [x] One atomic `find_one_and_update` upsert per report (repeats become confirmations); `$geoWithin` viewport query; `$group` summary pipeline
- [x] API: `POST /api/reports`, `GET /api/reports?bbox=`, `GET /api/reports/summary`, `GET /api/segments/{id}/reports`; routes carry reports on the recommended route
- [x] UI: "Report a street issue" chips on the street sheet, violet dots on the map, a line on the route card; hidden in `?demo=1`
- [x] `check_keys` MongoDB line (ping + indexes); `MONGODB_URI` pattern in `deploy/capture_keys.py`
- [x] Free M0 cluster `pathpulse` (AWS us-east-1) live; `MONGODB_URI` in `backend/.env`; `/healthz` reports `ok`; live end-to-end test passed (report, confirmation, viewport, summary)
- [x] Vultr VM IP (155.138.233.35) allowed in Atlas → Network Access
- [ ] Demo it in the video: report "Crossing signal out" on a street, then show the dot on the map and the line on the route card

## Personal-safety extension (added Sep 26)
- [x] Safety layer live: lighting, foot traffic, help points (100 GT blue-light phones + police, fire, hospitals, MARTA), and APD crimes against persons (informational, hex × day-part, fairness note; never used for routing)
- [x] "Well-lit & busier (after dark)" route preference; Share my walk + late check-in
- [x] Model card and PRD amended; independent code review: no critical issues, all findings fixed
- [ ] In the demo video and Devpost: show the fairness safeguards explicitly (judges will ask)

## Ride mode (added Sep 26 evening)
- [x] Walk · Bike · E-bike · Scooter live on pathpro.tech (bundle pp-20260926-1902-f49c0d2); ride model 69.9% [64.0–76.1] vs HIN 43.6%, past bike crashes 30.4%, random 12.0% (2024, 174 cyclist crashes)
- [x] MARTA hand-off + "Try Bike" on long walks; 28 rail stations
- [x] Offline demo includes ride routes

## Submission
- [ ] Devpost: every category above, the AI-tool disclosure and data credits (already in `docs/devpost.md`)
- [x] Demo video v2 (6:12): media/pathpro_demo_v2.mp4 + captions media/pathpro_demo_v2.srt/.vtt + thumbnail media/thumbnail_v2.png — CodingClaws intro, motivation, risks (traffic, reported crimes, lighting, weather, hazards), who it's for, usability, ROI, one scene per sponsor
- [ ] Upload the video to YouTube (attach the .srt), paste the link into Devpost
- [ ] (old) Demo video (2–3 min): live route, Risk Tides, "Why?" sheet with Tiger history, Listen (ElevenLabs), pathpro.tech in the address bar
- [ ] Submit the Devpost link at expo.hexlabs.org
- [ ] Expo kit: laptop on `?demo=1`, phone on pathpro.tech, QR code, model card, judge Q&A (`docs/judge_qa.md`)
- [ ] Afterwards: turn off Chrome's View → Developer → "Allow JavaScript from Apple Events"

Groq (`openai/gpt-oss-120b`) runs the main explanations but has no HackGT prize category. It's listed under "Built with" only.
