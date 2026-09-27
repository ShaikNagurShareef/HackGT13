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
