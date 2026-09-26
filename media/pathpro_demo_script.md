# PathPro demo video: narration script

- **Main cut:** `media/pathpro_demo.mp4`, 2:46, 1920×1080, 30 fps, H.264 + AAC, narration at about −16 LUFS.
- **30-second cut:** `media/pathpro_30s.mp4`, 0:31.
- **Narration:** ElevenLabs text-to-speech (`eleven_multilingual_v2`, the app's own "Sarah" voice), one clip per scene.
- **Footage:** screen captures of https://pathpro.tech.
  - The deterministic scenes use the offline scripted demo (`?demo=1`: Klaus Building to Midtown MARTA, Friday 10:30 PM, wet).
  - The GPS scene uses the live site with the browser's location set to Georgia Tech.
  - Phone scenes are Pixel 7 emulation. Desktop scenes are 1440×900.
- **Share my walk** is recorded in demo mode, where sharing is simulated on the device. No shared walks or street reports were written to the production database.

Timestamps below are when each line of narration starts in the main cut.

## Main cut (2:46)

| Time | Scene | On screen | Narration |
| --- | --- | --- | --- |
| 0:00 | Hook | Desktop Risk Tides playing through a Friday across the whole city, then zooming into Midtown. The title card reads "PathPro: See traffic risk before you walk into it." | Pedestrian deaths in Atlanta are a public-health problem. But traffic risk isn't spread evenly. It spikes on certain streets, at certain hours, in certain weather. Map apps optimize one number: time. PathPro shows you the risk they leave out. |
| 0:18 | GPS start (live site) | Phone: tap "Where to?", pick Midtown MARTA, and the route starts from "Your location". | On your phone, open pathpro.tech, tap Where to, and pick Midtown MARTA. It starts from your GPS location, just like the map apps you already use. |
| 0:28 | Route card | Phone, demo: "23 min · 54% less traffic risk · +4 min vs fastest". The caption shows **54% less traffic risk, +4 min**. | Here's Klaus to Midtown MARTA at ten-thirty on a rainy Friday night. The teal PathPro route is about four minutes longer than the fastest walk, with fifty-four percent less traffic risk. |
| 0:40 | Why? + Listen | Tap "Why?": the explanation and the avoided stretches (Peachtree Place NW 100, 8th Street NW 97). Then tap "Listen". | Tap Why, and it names the high-risk stretches it avoids. Tap Listen, and ElevenLabs reads it aloud. |
| 0:47 | Listen (app voice) | The same sheet stays up while the explanation is read aloud. | *The PathPro route adds 4.2 minutes and cuts traffic-risk exposure 54 percent by avoiding Peachtree Place Northwest and Williams Street Northwest. Both routes use Fifth Street Northwest, so stay alert there.* |
| 1:02 | Navigation + Share my walk | Tap "Start". The "High traffic risk ahead" banner appears, then "Share my walk" changes to "Sharing live" with the notice "Live link shared." | Start navigation, and PathPro warns you out loud before each high-traffic-risk crossing. Share my walk sends a friend a live link, and if you're running late, it checks in on you. |
| 1:14 | Risk Tides | Desktop, whole city: drag the hour slider from 6 AM to 11 PM on Dry, then switch to Wet. | On desktop, Risk Tides re-scores about fifty thousand Atlanta streets for every hour and weather, on one citywide scale. Watch corridors light up after dark, and again when the pavement turns wet. |
| 1:27 | Why this street? | Click Peachtree Place NW to open the sheet: score 100, and factor bars +56 +32 +9 +1 +2 = 100. | Click any street to see why. The score splits exactly into its causes, and the bars always add up. Groq or Gemini writes the sentence, but only from the model's evidence. The LLM never produces a number. |
| 1:41 | City Pulse | Switch the map mode to City Pulse: area scores for the whole city on a Friday evening. | City Pulse scores all 3,537 areas of the city, so any address gets a score. |
| 1:48 | Personal safety | Friday 10 PM. Personal safety mode shows help points, including GT blue-light phones, then the sidebar scrolls to the fairness note and sources. | Walking at night is about more than traffic. Personal-safety mode adds street lighting, foot traffic, and help points, including Georgia Tech's blue-light phones. Reported crimes against persons are informational only, shown with a fairness note, and never used to choose routes. |
| 2:07 | Does it work? | Animated chart of the 2024 holdout: PathPro 74.3% (95% CI 70.5–78.3%), City High Injury Network 53.8%, past-crash ranking 49.8%, random 11.9%. | Does it work? We trained on 2020 to 2023, and tested on 543 pedestrian crashes from 2024 the model never saw. The ten percent of streets PathPro ranks highest held seventy-four percent of them. The City's High Injury Network: fifty-four. Random: twelve. |
| 2:28 | Sponsors + close | Sponsors fade in one by one, then the tagline and the "Always stay alert / call 911" line. | PathPro runs on Vultr at pathpro.tech, with crash history in Tiger Data, community reports and shared walks in MongoDB Atlas, explanations from Groq and Gemini, and voice by ElevenLabs. See traffic risk before you walk into it. |

The sponsor card on screen lists what each sponsor does:

- **Vultr:** hosts the API and site (Atlanta VM, Caddy, systemd).
- **.tech:** pathpro.tech, "path protect".
- **Tiger Data:** crash hypertable, hourly aggregates, PostGIS risk grid.
- **MongoDB Atlas:** community street reports and Share my walk live links.
- **Gemini + Groq:** grounded explanations, validated against the evidence.
- **ElevenLabs:** Listen and spoken walk alerts.

## 30-second cut (0:31)

| Time | On screen | Narration |
| --- | --- | --- |
| 0:00 | Risk Tides over the whole city, with the title card | Map apps optimize for time. PathPro adds what they leave out: pedestrian traffic risk. |
| 0:06 | Phone route card, **54% less traffic risk, +4 min** | Klaus to Midtown MARTA on a rainy Friday night: a route four minutes longer, with fifty-four percent less traffic risk. |
| 0:13 | Street sheet with factor bars | Tap any street to see exactly why. |
| 0:16 | 2024 holdout chart | On 2024 crashes it never saw, the ten percent of streets it ranks highest held seventy-four percent of pedestrian crashes. The City's High Injury Network: fifty-four. |
| 0:26 | Sponsor card and tagline | PathPro. See traffic risk before you walk into it. |

## Sources for every number

- **Route numbers** (23 min, 54% less traffic risk, +4 min, and the 4.2 min in the explanation) are the app's own output for the scripted demo route.
- **Factor bars** (56 + 32 + 9 + 1 + 2 = 100 for Peachtree Place NW) are the app's own output, as shown in the demo.
- **Holdout metrics** come from `docs/metrics.json` (`spatial_test`) and `docs/model_card.md`:
  - capture of the top 10% of street length: 0.743 [0.705, 0.783]
  - High Injury Network 0.538, past-crash ranking 0.498, random 0.119
  - 543 observed pedestrian crashes in 2024
  - ROC-AUC 0.889
  - 2023 holdout: 0.681 vs HIN 0.542
- **Coverage numbers:** "about 50,000 streets" is 49,915 road segments, and "3,537 areas" is the number of City Pulse H3 cells (README and model card).
- **Temporal effects** in the Risk Tides caption (darkness ×1.6, wet pavement ×1.12) come from the model card.

## Wording rules followed

- The script says "traffic risk", "lower-risk", and "reported crimes against persons".
- It never says "safe", "safest", "unsafe", "dangerous area", or "guaranteed".
- The LLM never produces a number: the explanation read aloud is the app's validated explanation text for the demo route.

---

# v2: full demo with team intro, captions, motivation, risks, ROI and sponsor section (6:30)

- **Video:** `media/pathpro_demo_v2.mp4`, 1920×1080, 30 fps, H.264 + AAC, mixed to about −16 LUFS.
- **Captions:** burned into the video, and also available as `media/pathpro_demo_v2.srt` and `media/pathpro_demo_v2.vtt`.
- **Voice:** ElevenLabs `eleven_multilingual_v2` with the same "Sarah" voice. Lines in *italics* are the app's own spoken output (Listen and walk alerts), filtered slightly so they sound like a phone speaker.
- **Music:** a soft ambient bed, synthesized locally, sits about 20 dB under the voice and dips further while anyone is speaking. The API key lacks the ElevenLabs sound-generation permission, so that route wasn't available.
- **Captions are timed from the audio.** New clips use ElevenLabs character timestamps; clips carried over from v1 are timed from their pauses. Each caption has at most 2 lines of 42 characters.
- **Footage:**
  - **Live site** https://pathpro.tech (model `pp-20260926-1902-f49c0d2`): the GPS start, routine card, Ride mode + MARTA hand-off, Well-lit & busier at 10:30 PM, the late check-in, and the street sheet with the Groq explanation, Tiger Data chart and report chips.
  - **Offline demo** `?demo=1`: everything else.
  - **Nothing written to production.** No community reports or shared walks were created. Share my walk comes from demo mode. The routine card lives only in the browser's local storage. The check-in dialog is on-device, reached by fast-forwarding the browser clock.

| Time | Scene | On screen | Narration |
| --- | --- | --- | --- |
| 0:00 | team | Title card: “CodingClaws at HackGT 13 presents PathPro”, the tagline, and the team: Nagur Shareef Shaik · Sahith Reddy Thummala · Pranav Nagothu · Geethanjali Nagaboina. | We're CodingClaws: Nagur, Sahith, Pranav, and Geethanjali. And this is PathPro. |
| 0:06 | open | Desktop Risk Tides with the title card, then the phone preview walk at night: “Why we built PathPro”. | Pedestrian deaths in Atlanta are a public-health problem. Many of us walk between Klaus, Tech Square, and Midtown MARTA late at night. Our friends, especially women, already plan routes around well-lit, busier streets, and text each other when they get home. Yet every navigation app asks one question: what's fastest? So we built PathPro: one map of the risks on your way, from traffic and darkness to reported crimes and street hazards, with better tools for getting around alone at night. |
| 0:37 | diff | Comparison card (generic categories, no brands): Map apps: fastest route only · Crime maps: label whole neighborhoods · Location-sharing apps: no route · highlighted PathPro row: lower-risk routes · every risk on one map · explained & fair · walk + ride + MARTA. | Map apps optimize for time. Crime maps label whole neighborhoods. Location-sharing apps don't plan your route. PathPro does it together, honestly: a crash-trained model that beats the City's own High Injury Network, explains every score, and never routes around neighborhoods. |
| 0:55 | usability | Live phone: Where to? → Midtown MARTA from “Your location” (two taps). Then the desktop sidebar, then the on-device routine card “Heading back to Klaus Building?”. | Open pathpro.tech in any phone browser. There's no app to install and no login. Two taps take you from opening it to a route that starts at your GPS location. It works on desktop too, with keyboard and screen-reader labels and large touch targets, and your walking patterns stay on your phone. |
| 1:14 | route | Demo route card: 23 min · **54% less traffic risk** · +4 min vs fastest. | Here's Klaus to Midtown MARTA at 10:30 on a rainy Friday night. The teal PathPro route is about four minutes longer than the fastest walk, with 54% less traffic risk. |
| 1:26 | why | Why? sheet: the avoided stretches Peachtree Place NW (100) and 8th Street NW (97). Listen plays the app voice (excerpt). | Tap Why, and it names the high-risk stretches it avoids. Tap Listen, and ElevenLabs reads it aloud. *The PathPro route adds 4.2 minutes and cuts traffic-risk exposure 54%…* |
| 1:40 | nav | Preview walk with the “High traffic risk ahead” banner and the spoken alert. | Start navigation, and PathPro walks with you, speaking up before each high-traffic-risk crossing. *High traffic risk ahead. Fowler Street Northwest and Ferst Drive Northwest, in 250 m.* |
| 1:52 | modes | Live Georgia Tech → Inman Park MARTA: an 84 min walk with “Faster with MARTA: walk 17 min to Midtown station” and “Try Bike: ~25 min”. Then the Bike tab: **27 min ride · 72% less traffic risk**, +4 min. | On a long walk, like Georgia Tech to Inman Park, PathPro offers a faster option: walk 17 minutes to Midtown station and take MARTA. Or switch to Bike, E-bike, or Scooter. This ride takes 27 minutes, with 72% less traffic risk than the fastest ride. |
| 2:11 | risks | Risks segment: personal-safety map (indigo hexes by day part, help points, fairness note) → live Why? factor bars → Risk Tides scrub and Dry → Wet → Well-lit & busier → live report-a-hazard chips (not submitted) → Bike route (ride model with bike-lane data). | PathPro shows more than traffic. It maps reported crimes against persons: homicide, robbery, and assault, from Atlanta Police open data, grouped by area and time of day, with no addresses or victim details. Bands account for foot traffic, so an area with no reports is never marked higher, and a fairness note is always on screen. Crime is never used to choose your route: a test multiplies crime counts by 1,000, and the routes don't change. Traffic risk comes from vehicle crashes, speed limits, lanes, traffic volume, and intersections. It rises after dark and on wet streets. Lighting and foot traffic shape the after-dark option. People report hazards like blocked sidewalks, crossing signals that are out, construction, flooding, and fast-moving traffic. And for riders, the ride model accounts for bike lanes. |
| 3:04 | who | Bike route (people on bikes and scooters) → live “Well-lit & busier (after dark)” toggle at 10:30 PM → “Sharing live” (demo) → “Everything OK?” late check-in (live, on-device, reached with a fast-forwarded clock) → voice-alert banner. | PathPro is for anyone walking or riding alone at night: women and girls, students, people who rely on MARTA instead of a car, older adults, and people on bikes and scooters. Choose well-lit and busier streets after dark, with help points like Georgia Tech's blue-light phones along the way. Share my walk lets a friend follow along, and if you're running late, PathPro checks in, with 911 one tap away. And voice alerts keep your eyes up, not on the screen. |
| 3:33 | city | City Pulse area scores for the whole city. | City Pulse scores all 3,537 areas of the city, so any address gets a score. |
| 3:40 | metric | Walk holdout chart: PathPro **74.3%** [70.5–78.3] · HIN 53.8% · past pedestrian crashes 49.8% · random 11.9%. | Does it work? We trained on 2020 to 2023, and tested on 543 pedestrian crashes from 2024 the model never saw. The 10% of streets PathPro ranks highest held 74% of them. The City's High Injury Network: 54%. Random: 12%. |
| 4:01 | roi | ROI card: walk 74.3% vs HIN 53.8% (**+38%**); ride 69.9% vs HIN 43.6% (**+60%**); +4 min › 54% less; **$340 billion** (NHTSA 2019, cited on screen); one coverage polygon per city. | What does better ranking buy? For a city, the same budget spent on 10% of street length reaches 38% more of next year's pedestrian crashes than the High Injury Network, and, for rides, about 60% more bike crashes. For a person, four extra minutes cut traffic-risk exposure by more than half. Nationally, NHTSA puts the economic cost of crashes at $340 billion in 2019. And a new city needs one coverage polygon, plus its public crash data. |
| 4:35 | arch | Architecture: public data → clean + snap → models → bundle → FastAPI → React/MapLibre on a Vultr VM, with Tiger Data, MongoDB Atlas, Groq › Gemini and ElevenLabs around it. | Under the hood, we clean a quarter million public crash records, snap them to 50,000 streets, and score each one by hour and weather. One bundle feeds a FastAPI service and a React map. |
| 4:48 | vultr | **Vultr:** terminal card from real read-only `dig` and `curl` output (155.138.233.35; healthz ok with walk + ride; ~0.2 s; HTTP/2 + HSTS). Stack: Vultr VM in Atlanta · Caddy auto-HTTPS · systemd + ufw · `deploy/go.sh pathpro.tech`. | Vultr runs all of it: the API and the site, on one VM in Atlanta, close to our users. Caddy adds automatic HTTPS, systemd keeps it up, and one script deploys it. |
| 5:01 | tech | **.tech:** pathpro.tech → “path protect”. | Our domain is pathpro.tech. Say it out loud: path protect. The .tech completes the word. |
| 5:08 | tiger | **Tiger Data:** live street sheet “When crashes happened here · Tiger Data”, then a card: 220,594 rows / 57 chunks · `crashes_hourly` · PostGIS 49,915 segments · 9,583,680-row risk grid. | Tiger Data is our system of record: over 220,000 crash rows in a Timescale hypertable, a continuous aggregate behind each street's crashes-by-hour chart, PostGIS geometry, and a risk grid of 9.5 million rows. |
| 5:25 | mongo | **MongoDB Atlas:** live “Report a street issue” chips (not submitted), then a card: 2dsphere `$geoWithin` · 14-day TTL · atomic upsert confirmations · `$group` summary · Share my walk TTL 6 h, hashed tokens, optimistic concurrency. | MongoDB Atlas holds what walkers tell us. Street reports use a geo index for map queries, expire after 14 days, and repeats become confirmations in one atomic upsert. Shared walks expire in 6 hours. Geo plus TTL fits short-lived, user-generated data. |
| 5:45 | eleven | **ElevenLabs:** navigation banner, with the real alert clip replayed. | ElevenLabs gives PathPro its voice, for explanations and for walk alerts like this one. *High traffic risk ahead. Fowler Street Northwest and Ferst Drive Northwest, in 250 m.* |
| 5:57 | llm | **Groq + Gemini:** live Groq explanation on the street sheet, then the pipeline card: evidence JSON → Groq gpt-oss-120b → Gemini fallback → validator → sentence or template. | Explanations come from Groq's GPT-OSS 120B, for sub-second answers, with Gemini as the fallback. A validator rejects any sentence with a number that isn't in the evidence, so the LLM never produces a risk number. |
| 6:14 | close | End card: PathPro · “See the risks on your way, before you go.” · Walk · Bike · E-bike · Scooter · pathpro.tech · github.com/ShaikNagurShareef/PathPro · Built by CodingClaws at HackGT 13 · Nagur Shareef Shaik · Sahith Reddy Thummala · Pranav Nagothu · Geethanjali Nagaboina · 911 line (held about 5 s). | That's PathPro: the risks on your way, for every street, every hour, and every way you get around Atlanta. Try it at pathpro.tech. See the risks on your way, before you go. |

## v2 sources for every number

- **Walk holdout:** `docs/metrics.json` `spatial_test`: capture of the top 10% of street length 0.743 [0.705, 0.783]; HIN 0.538; past-crash ranking 0.498; random 0.119; 543 crashes; ROC-AUC 0.889.
- **Ride model:** `modes.ride.headline` in the deployed manifest `artifacts/pp-20260926-1902-f49c0d2/manifest.json`: 0.699 [0.640, 0.761] vs HIN 0.436 (past bike crashes 0.304, random 0.120, 174 cyclist crashes, 2024). It is trained on pooled pedestrian + cyclist crashes and scored on cyclist crashes only, so the video claims a ranking, not a calibrated count.
- **ROI "more crashes reached for the same budget":** these are ratios of the capture rates above.
  - Walk: 0.743 / 0.538 = 1.38, so +38%.
  - Ride: 0.699 / 0.436 = 1.60, so +60%.
  - "Budget" means treating the same 10% of street length.
- **National cost:** NHTSA, *The Economic and Societal Impact of Motor Vehicle Crashes, 2019 (Revised)*, DOT HS 813 403, Feb 2023. The abstract says: "The economic costs of these crashes totaled $340 billion… the total value of societal harm… was nearly $1.4 trillion." I fetched and checked it from the primary source on Sep 26, 2026.
- **"One coverage polygon":** `docs/devpost.md` says "a new city needs one coverage polygon plus its public crash layers."
- **Route and ride numbers** were read from the app at recording time.
  - Demo route: 23 min, 54%, +4 min, 4.2 min.
  - Live, Sat Sep 26 around 3:45 PM: Georgia Tech → Inman Park MARTA walk 84 min, with MARTA via Midtown station after a 17 min walk; Bike 27 min ride, 72% less traffic risk, +4 min.
  - Live Georgia Tech → Midtown MARTA at 10:30 PM: 22 min, 54% less traffic risk.
- **Tiger Data:** `docs/images/gallery/README.md` and `docs/sponsor_checklist.md`: 220,594 rows, 57 chunks, `crashes_hourly`, 9,583,680 risk-grid rows, 49,915 segments.
- **Vultr:** the terminal lines are real output of read-only `dig` and `curl` against the live site on Sep 26. The VM facts come from `docs/sponsor_checklist.md` and `deploy/go.sh`.
- **MongoDB Atlas:** README.md "Sponsor technology" and `docs/sponsor_checklist.md`.
- **Crime layer and safeguards:** `docs/model_card.md` "Personal-safety layer".
  - The data is Atlanta Police open data: homicide, robbery, aggravated and simple assault.
  - Residences, jails and shelters are excluded. Only date, offense and location type are fetched.
  - Bands are an Empirical-Bayes rate per unit of pedestrian activity. "Higher" needs at least one report and a 90% posterior, so a hex with no reports is never "higher".
  - The layer is never used in routing, and a test scales crime counts by 1,000 and checks that routes are unchanged.
- **Bike lanes in the ride model:** `data/src/pathpulse_data/ride/run.py` and `ride/features.py` use OSM and City bike-infrastructure classes.
- **"Beats the City’s own High Injury Network":** walk model 74.3% vs HIN 53.8% capture at 10% of street length (2024 holdout, `docs/metrics.json`).
- **Tagline:** "See the risks on your way, before you go." It matches the app and docs.
- **Motivation:** the framing the team chose (no specific incident or person is described). The video uses "we", and Claude Code is disclosed only where it already was (README / Devpost).

## v2 30-second cut (0:35)

The 30-second cut is `media/pathpro_30s.mp4`, with captions burned in and in `media/pathpro_30s.srt`. It uses the same pipeline, music bed and caption style as v2. The differentiation line didn't fit within about 35 s, so it's only in the full cut.

| Time | On screen | Narration |
| --- | --- | --- |
| 0:00 | Team card: CodingClaws at HackGT 13 presents PathPro, with the four names | We're CodingClaws: Nagur, Sahith, Pranav, and Geethanjali. And this is PathPro. |
| 0:05 | Risk Tides across the whole city, with the title and tagline | One map of the risks on your way: traffic, darkness, reported crimes, and street hazards. For walking, biking, and scooters. |
| 0:13 | Phone route card: **54% less traffic risk**, +4 min | Klaus to Midtown MARTA on a rainy Friday night: a route four minutes longer, with 54% less traffic risk. |
| 0:20 | 2024 holdout chart: PathPro 74.3% [70.5–78.3] vs HIN 53.8% | On 2024 crashes it never saw, the 10% of streets it ranks highest held 74% of pedestrian crashes. The City's High Injury Network: 54%. |
| 0:30 | End card: tagline, pathpro.tech, GitHub, CodingClaws credits | PathPro. See the risks on your way, before you go. |
