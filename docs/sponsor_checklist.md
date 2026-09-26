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
- [x] Account created and logged in
- [ ] **Apply the MLH gift code** at Vultr → Billing → Gift Code (code in the MLH email "Everything you'll need to know from MLH at HackGT 13", or ask the MLH coach). Blocking: Vultr won't enable the API on an unfunded account.
- [ ] Enable API access, create the key, save `VULTR_API_KEY`
- [ ] `deploy/go.sh pathpro.tech`: create the VM (Atlanta region), bootstrap, deploy with Caddy and systemd, load Tiger, smoke-test
- [ ] Stop the laptop tunnel (`deploy/tunnel_watchdog.sh`) once Vultr serves the app
- [ ] If Vultr isn't live by submission, remove the "Vultr hosts…" claim from `docs/devpost.md` and the README

### .tech domains: Best .tech Domain
- [ ] Get the .tech code from the same MLH email
- [ ] Register **pathpro.tech** ("path protect", a pun as the MLH coach asked) at get.tech with the code from the MLH email. Checked Sep 26: available; backups `walkpro.tech`, `pathde.tech` ("path detect")
- [ ] Add an A record pointing to the Vultr VM IP; Caddy issues HTTPS automatically
- [ ] Confirm https://pathpro.tech loads the app

### ElevenLabs: Best Use of ElevenLabs
- [x] Free-tier key, restricted to text-to-speech, voices (read), models and user
- [x] Voice "Sarah" (reassuring, calm), `ELEVENLABS_VOICE_ID` set
- [x] Live: `POST /api/tts` returns MP3 for "Listen" and walk alerts; it speaks only server-written text
- [ ] Show "Listen" with audio on in the demo video

### Gemini API: Best Use of Gemini API
- [x] Key saved (free tier, "HackGT" key in AI Studio) and verified
- [x] Second provider in the explanation chain (Groq → Gemini → template), under the same validator
- [ ] Confirm at the MLH table that this prize is offered at HackGT 13 (it's on the MLH page but not on Devpost)

## HackGT tracks and other sponsors

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

## Submission
- [ ] Devpost: every category above, the AI-tool disclosure (Claude Code + ECC) and data credits (already in `docs/devpost.md`)
- [ ] Demo video (2–3 min): live route, Risk Tides, "Why?" sheet with Tiger history, Listen (ElevenLabs), pathpro.tech in the address bar
- [ ] Submit the Devpost link at expo.hexlabs.org
- [ ] Expo kit: laptop on `?demo=1`, phone on pathpro.tech, QR code, model card, judge Q&A (`docs/judge_qa.md`)
- [ ] Afterwards: turn off Chrome's View → Developer → "Allow JavaScript from Apple Events"

Groq (`openai/gpt-oss-120b`) runs the main explanations but has no HackGT prize category. It's listed under "Built with" only.
