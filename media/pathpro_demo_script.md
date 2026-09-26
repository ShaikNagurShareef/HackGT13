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
