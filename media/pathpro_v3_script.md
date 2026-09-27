# PathPro v3 demo video (3:00), solo cut

- **Maker:** Nagur Shareef Shaik (team name Coding Claws, Georgia State University), HackGT 13. Solo build.
- **Voice:** Grok Voice TTS (`POST https://api.x.ai/v1/tts`), voice **orion**. The script uses Grok's expressive tags (`[pause]`, `[breath]`, `<soft>…</soft>`). Captions are timed from `with_timestamps`.
- **Disclosure:** a small on-screen caption at 0:00–0:06 reads "Narration: Grok Voice (AI)". The narrator speaks as the maker, but it is not the maker's recorded voice.
- **Format:** 1920×1080, 30 fps, H.264 + AAC. Narration sits at about −16 LUFS over a soft music bed about 20 dB under the voice. Captions are burned in and also shipped as `.srt` and `.vtt`.
- **Footage:**
  - Live https://pathpro.tech: GPS start, Grok explanation, Imagine with the Gemini check, Ask PathPro.
  - `?demo=1`: the deterministic route, navigation preview, and Share my walk.
  - Nothing is written to production (no reports or shared walks).
  - Phone scenes use Pixel 7 emulation; desktop scenes are 1440×900.
- **Rules:**
  - Copy: "traffic risk", "lower-risk"; never "safe/safest/unsafe/dangerous area/guaranteed".
  - Crime data is only ever described as informational.
  - Every number comes from `docs/metrics.json` or the live app.

| Time | Scene | On screen | Narration (Grok Voice, orion) |
| --- | --- | --- | --- |
| 0:00 | Hook | Night map of Atlanta: Risk Tides sweeping through the evening; streets glow as risk rises. Caption: "Narration: Grok Voice (AI)". | Every map app answers one question. [pause] What's fastest? <soft>But when you're walking home at night, that's not the question you're really asking.</soft> |
| 0:10 | The problem | Pedestrian crashes concentrating on a few corridors (Risk Tides zoom), then a phone showing a plain "fastest" route. | In Atlanta, pedestrian crashes pile up on a small share of streets, and the risk rises and falls with the hour and the weather. My friends already plan around it by instinct: well-lit streets, busier streets, texting when they get home. [pause] Nobody had built a map for that. |
| 0:28 | Me | Title card: "PathPro · See the risks on your way, before you go." Subtitle: "Built solo by Nagur Shareef Shaik · HackGT 13". | I'm Nagur Shareef Shaik. I built PathPro, solo, this weekend. |
| 0:34 | Two taps | Phone (live): Where to? → Midtown MARTA, starting from "Your location". Route card: **23 min · 54% less traffic risk · +4 min**. | Open pathpro.tech. No app, no account. Two taps, and you get a route that costs four extra minutes and cuts your traffic-risk exposure by fifty-four percent. |
| 0:46 | Navigation voice | Preview walk with the banner "High traffic risk ahead" and a real Grok Voice alert clip. | Then it walks with you. [pause] *High traffic risk ahead. Tenth Street Northwest.* Eyes on the street, not the screen. |
| 0:56 | Why? | Street sheet: factor bars that add up exactly to the score, crashes by hour (Tiger Data), then a Grok explanation with Listen. | Tap any street to see why. The factors add up exactly to the score, and Grok explains it in plain words. But Grok can't invent a single number: if a sentence isn't backed by the evidence, it never reaches your screen. |
| 1:12 | Every way you move | Bike tab: **28 min ride · 72% less traffic risk**; then a long walk showing the MARTA hand-off. | Riding? Bike, e-bike and scooter get their own crash model: seventy-two percent less traffic risk for four extra minutes. Long walk? It hands you off to MARTA. |
| 1:24 | Walking alone at night | "Well-lit & busier" toggle, help points (Georgia Tech blue-light phones), crime layer with the fairness note, Share my walk, the "Everything OK?" check-in. | After dark, choose well-lit, busier streets, with help points along the way. Share your walk with a friend, and if you're running late, PathPro checks in. Reported crimes are shown for context, with a fairness note, and they never, ever choose your route. |
| 1:44 | Imagine the fix | Street sheet → "Imagine this street redesigned" → Grok Imagine picture with the label, then "Checked by Gemini: shows 3 of 3 planned fixes". | And for the people who fix streets: [pause] tap "Imagine this street redesigned". Grok Imagine draws the fixes this exact street needs, like crosswalks, curb extensions and lighting. Then Gemini checks the picture before anyone sees it. See the change before a dollar is spent on concrete. |
| 2:04 | Ask PathPro | Ask about this street → context chip → answer grounded in the factors; then the "Remember my preferences" switch and Forget me. | Still curious? Ask PathPro. Built on Backboard, it answers from my model's own documents and whatever street, route or area you're looking at. Turn on memory and it remembers how you like to travel. Tap Forget me, and it's gone. |
| 2:22 | Proof | Holdout chart: PathPro **74.3%** vs High Injury Network 53.8% vs random 11.9% (95% CI shown). ROI card: **~38% more crashes reached, same budget**. | Does it work? I trained on 2020 to 2023 and tested on 2024, a year the model never saw. The ten percent of streets PathPro flags held seventy-four percent of pedestrian crashes. The City's own High Injury Network? Fifty-four. [pause] Same budget, about thirty-eight percent more crashes reached. |
| 2:42 | Built to last | Stack strip: Vultr (Atlanta), pathpro.tech, Tiger Data, MongoDB Atlas, xAI Grok, Gemini, Backboard, ElevenLabs. "Works offline." | It runs on Vultr in Atlanta, keeps working when any service fails, and its demo mode even works offline. |
| 2:50 | Close | End card: PathPro · "See the risks on your way, before you go." · pathpro.tech · github.com/ShaikNagurShareef/PathPro · Nagur Shareef Shaik · Coding Claws · HackGT 13. | [breath] <soft>Mission control for every walk home.</soft> PathPro. See the risks on your way, before you go. |

## Sources for every number
- 54% less traffic risk for +4 min (Klaus → Midtown MARTA, Friday 10:30 PM, wet): offline demo and live route card.
- 72% less for +4 min (Georgia Tech → Inman Park by bike, 9 PM): live route card.
- 74.3% [70.5–78.3] vs HIN 53.8%, random 11.9% (2024 holdout): `docs/metrics.json`.
- About 38% more crashes reached for the same budget: 74.3 / 53.8 − 1 = 38.1%.
- "Checked by Gemini: shows 3 of 3 planned fixes": the Williams Street NW illustration (`docs/images/gallery/11-imagine-street-redesign.png`), or a fresh live capture.

## v3 production notes

- **Files:** `media/pathpro_demo_v3.mp4` (3:01.7, 1920×1080, 30 fps, H.264 High + AAC 48 kHz), captions burned in and shipped as `media/pathpro_demo_v3.srt` / `.vtt`, thumbnail `media/thumbnail_v3.png` (1280×720).
- **Voice:** every scene is its own Grok Voice clip (`orion`, tags kept). Caption timing comes from `with_timestamps` (per-character times), at most 2 lines × 42 characters. The in-app alert is a separate Grok Voice clip (`eve`, the app's alert voice) with a phone-speaker EQ, captioned in italics. Nothing was sped up; pacing comes from the gaps.
- **Audio:** mix measured at −16.2 LUFS integrated (two-pass loudnorm, −1.5 dBTP). The music bed is synthesized locally (pad, arpeggio, reverb). It sits about 16 dB under the voice in pauses and about 22 dB under it while anyone speaks.
- **Scenes as cut:** 0:00 hook (desktop Risk Tides, 4 PM → 11 PM) · 0:10.6 problem (corridor zoom, then the plain fastest route) · 0:29.2 title card · 0:34.9 two taps (live GPS start at Klaus, Fri 10:30 PM wet → 23 min · 54% less · +4 min) · 0:46.4 preview walk + Grok Voice alert · 0:58.2 street sheet (factor bars, Tiger Data chart, Grok explanation) · 1:12.7 Bike tab + MARTA hand-off · 1:24.6 Well-lit & busier, help points, Share my walk (demo), "Everything OK?", crime layer with the fairness note · 1:41.8 Imagine (cached Williams Street NW picture, a 6 s Grok Imagine video labeled "AI illustration by Grok Imagine — not a real photo", "Checked by Gemini: shows 3 of 3 planned fixes") · 2:02.7 Ask PathPro (agent button → typing dots → answer; Ask about this street with the context pill; memory on → one generic preference → Forget me) · 2:18.8 holdout chart + ROI card · 2:41.6 stack · 2:49.9 end card.
- **Changed from the table above:** the live bike route came back as **23 min ride · 71% less traffic risk · +4 min** (Bobby Dodd Stadium on the Georgia Tech campus → Inman Park MARTA, Sat 9 PM), so the narration says "seventy-one percent" and the caption matches. The long walk shows "Faster with MARTA: walk 9 min to North Avenue station". The alert names the street the demo walk actually reaches ("Fowler Street Northwest and Ferst Drive Northwest, in 300 meters"), not Tenth Street.
- **Footage:** recorded locally against the new UI (Ask agent button, bigger mode icons) with Playwright on GPU Chromium: a CDP screencast at full device resolution (Pixel-7-like 390×844 at dpr 2; desktop 1440×900 with the sidebar hidden for full-bleed map shots). Nothing was written to production. Share my walk is the demo's on-device simulation; headless Chromium has no OS share sheet, so `navigator.share` was stubbed for the recording. The check-in was reached by fast-forwarding the browser clock. Ask memory was turned on for one generic preference, then deleted with Forget me.
- **Cosmetic workaround:** the new "Forget me" control rendered as an empty white box (its `text-btn` class has no styles), so the recording injected the app's own `.link-btn` look for that button. This should be fixed in the app.
- **Cost:** about $0.49 for the one Grok Imagine video, plus a few cents of Grok Voice, Grok explanations and Backboard answers. No new Grok Imagine images were generated.
