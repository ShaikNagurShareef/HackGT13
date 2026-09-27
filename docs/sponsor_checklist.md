# Sponsor and prize checklist

Status as of Sat Sep 26, 2026, late evening ET. Solo build (team name Coding Claws, Georgia State University). Submit on Devpost by **Sun 07:30** (hacking ends 08:00), then add the link at expo.hexlabs.org. Expo: Sun 09:30–11:00, Klaus Atrium.

`[x]` done (verified live on pathpro.tech unless it says "locally") · `[ ]` still to do

**Not yet deployed:** Grok (explanations, Grok Voice, Grok Imagine), the Gemini image check, and Ask PathPro (Backboard) are built and tested, and Grok, Gemini, and Backboard were verified against the real APIs locally. The next deploy with `deploy/go.sh pathpro.tech` puts them live.

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
- [x] Gemini image check verified against the real API locally (`gemini-3.1-flash-lite`, its own model setting)
- [x] Prize is offered: "Best Use of Gemini API" is on the Devpost form, ticked; Gemini project number submitted on the form
- [ ] Deploy the image check to pathpro.tech and take the "Checked by Gemini" gallery screenshot

### Backboard: Best Use of Backboard ("Ask PathPro")
Job: answer questions about how PathPro works, and about the street, route, or area on screen, only from PathPro's own docs and server-built evidence. It never scores a street and never touches routing.
- [x] `POST /api/ask` on Backboard's `/threads/messages`. Public questions go to the shared docs assistant with `memory: "Readonly"`, so no visitor can write its memory. Thread tokens are signed by the server and bound to their assistant; a forged or mismatched one starts a new thread
- [x] **Ask PathPro v2:** "Ask about this street / route / area" entry points send server-built evidence (no coordinates) plus live conditions; answers cite their source docs
- [x] **Opt-in private memory** ("Remember my preferences", off by default): a private Backboard assistant clone per browser; keeps only stated travel preferences, never places; questions carrying street, route, or area context read memory but never write it; "Forget me" deletes the clone; a prune tool removes stale clones; clone creation is capped per visitor and per day
- [x] Every answer validated before it's shown (on topic, no outside links, banned words, crime framing, every number must appear in the docs or the on-screen evidence); failures, timeouts, and spent budgets return a fixed pointer to the model card, never raw LLM text
- [x] Limits: 20 questions per visitor per day (`ASK_PER_CLIENT_DAILY`), under a shared daily budget (`ASK_DAILY_BUDGET`)
- [x] Setup tool `python -m app.tools.setup_backboard`: strict system prompt, preference-only fact extraction prompt, curated corpus (model card, metrics, safety sources, decisions, data and models, judge Q&A), index polling, read-only facts in memory
- [x] "Ask PathPro" next to About (phone options sheet and desktop sidebar) with suggested questions; hidden in `?demo=1`; tests mock every Backboard call
- [x] `BACKBOARD_API_KEY` and `BACKBOARD_ASSISTANT_ID` set in `backend/.env`; assistant created and its documents indexed
- [x] Live test against the real Backboard API, locally: questions answered and validated, and opt-in memory kept a stated travel preference
- [ ] Deploy to pathpro.tech; `check_keys` shows Backboard OK on the VM; ask the suggested questions and one "Ask about this street" on pathpro.tech
- [ ] Only then tick "Best Use of Backboard" on the Devpost form and remove the ◇ markers in `docs/devpost_submission.md`

## HackGT tracks and other sponsors

### SpaceXAI "Make it Legendary" (Grok, Grok Imagine, Grok Voice; built with Cursor)
Pitch: *mission control for every walk home*. PathPro aligns with SpaceX's engineering culture (first principles, test like you fly, engine-out redundancy, reusability, public-health mission), not its branding. No logos, and no suggestion of a partnership.
- [x] xAI account (shaiknagurshareef6@gmail.com) and `XAI_API_KEY` in `backend/.env`; Grok verified against the real API locally
- [ ] Confirm the $25 credits from the SpaceXAI promo code are applied (Grok Voice + Imagine; code kept out of git)
- [ ] Actually do some PathPro work in Cursor (it is named in the Devpost AI-tools line and the SpaceXAI track asks for it). Until then, remove Cursor from that line
- [x] Built and tested: Grok explanations first in the chain (Grok → Groq → Gemini → template), Grok Voice alerts (ElevenLabs, then the device voice, as backups), and "Imagine this street redesigned" (Grok Imagine, server-built prompt, "not a real photo" label, checked by Gemini, per-visitor daily cap)
- [ ] Deploy to pathpro.tech and verify live: explanation source "grok", Grok Voice audio, one Imagine image with the "Checked by Gemini" line
- [x] Track selected on Devpost (sponsor track 2)
- [ ] Video v3: solo intro, Grok Voice narration, and the "Make it Legendary" scenes (script in `media/pathpro_demo_script.md`)
- [ ] Publish the "Make it Legendary" section in `docs/devpost.md` (gated on the live check)

### Oracle of the Deep (ML/AI + visualization)
- [x] Crash-trained model (GLM + LightGBM ensemble, Empirical Bayes) with spatial and temporal holdouts (`docs/model_card.md`)
- [x] Risk Tides: hourly and weather-aware map; factor bars add up exactly to each score
- [x] Selected on Devpost as the general track
- [ ] Put the headline metric in the first paragraph

### Aramco "A Marina's Mission" (social good)
- [x] Framing: pedestrian deaths as a public-health problem; traffic risk only, with no crime or demographic features
- [x] Selected on Devpost (sponsor track 1)

### Notability "Trust the Process"
- [x] Process notes with plan, milestones, model iterations, and timeline (`docs/process/process_notes.md` and PDF)
- [ ] Not selectable as a third sponsor track on the form (only two allowed); attach the PDF if the sponsor asks

### Create-X
- [ ] Tick the Create-X interest box on Devpost

### MongoDB Atlas: Best Use of MongoDB Atlas
- [x] Share my walk: `shared_walks` collection with a TTL index (6 h after last update), unique walk_id, hashed owner tokens, optimistic-concurrency updates; live on pathpro.tech
Job: community street reports. Tiger Data stays the system of record for crashes and scores; Atlas holds what walkers report, and it never feeds the model.
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
- [x] Devpost form answers entered: general track Oracle of the Deep; sponsor tracks Aramco (1st) and SpaceXAI (2nd); MLH ElevenLabs, Gemini API, TigerData, Vultr, MongoDB Atlas; school Georgia State University; domain pathpro.tech; the AI-tool disclosure and data credits
- [ ] Tick Backboard after the deploy; remove the ⚑/◇ gates in `docs/devpost_submission.md` once each feature is live
- [x] Demo video v2 (6:12): media/pathpro_demo_v2.mp4 + captions media/pathpro_demo_v2.srt/.vtt + thumbnail media/thumbnail_v2.png — team intro (outdated: it shows four people; PathPro is a solo build), motivation, risks (traffic, reported crimes, lighting, weather, hazards), who it's for, usability, ROI, one scene per sponsor
- [ ] Re-cut as v3 with a solo intro and the new features, then upload to YouTube (attach the .srt) and paste the link into Devpost
- [ ] (old) Demo video (2–3 min): live route, Risk Tides, "Why?" sheet with Tiger history, Listen (ElevenLabs), pathpro.tech in the address bar
- [ ] Submit the Devpost link at expo.hexlabs.org
- [ ] Expo kit: laptop on `?demo=1`, phone on pathpro.tech, QR code, model card, judge Q&A (`docs/judge_qa.md`)
- [ ] Afterwards: turn off Chrome's View → Developer → "Allow JavaScript from Apple Events"

Groq (`openai/gpt-oss-120b`) runs the main explanations but has no HackGT prize category. It's listed under "Built with" only.
