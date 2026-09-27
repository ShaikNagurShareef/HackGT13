# PathPro: Devpost submission (paste-ready)

Each section below is one field of the Devpost form, in the order Devpost asks for it. `docs/devpost.md` is the long draft this is condensed from; every number here comes from `docs/metrics.json` or the model card.

**Live status (Sat Sep 26, night):** Grok (explanations, Grok Voice, Grok Imagine), the Gemini image check, and Ask PathPro on Backboard are built and tested, and Grok, Gemini, and Backboard were verified against the real APIs locally. None of them is deployed to pathpro.tech yet.

**Before you paste:**
- [ ] Grok and the Gemini image check are deployed and verified live on pathpro.tech. If not, delete the "Grok" and "Gemini" lines marked ⚑ first.
- [x] Ask PathPro (Backboard) tested against the real API locally: `setup_backboard`, `check_keys`, real questions, and opt-in memory keeping a stated travel preference.
- [ ] Ask PathPro deployed and one real question answered on pathpro.tech. If not, delete the "Backboard" lines marked ◇ first, and don't tick the Backboard prize.
- [ ] Demo video uploaded to YouTube (unlisted is fine) with `media/pathpro_demo_v3.srt` attached.
- Solo build (team name Coding Claws), so there's no one to invite.

---

## 1. Project name

PathPro

## 2. Elevator pitch (≤ 200 characters)

Find a lower-risk way to walk or ride home in Atlanta. My crash model beats the City's own High Injury Network (74% vs 54%), and Grok shows what a fixed street could look like.

## 3. Thumbnail

`media/thumbnail_v3.png` (1280×720; Devpost crops thumbnails to 3:2, so check that the title stays visible in the preview).

## 4. About the project (paste as Markdown)

```markdown
**Try it:** https://pathpro.tech (add `?demo=1` for the offline demo) · **Code:** https://github.com/ShaikNagurShareef/PathPro

## Inspiration

I get around Atlanta on foot and on MARTA a lot, often late at night. My friends, especially women, already plan their walks around streets that are well lit and busy, and they text each other when they get home. Every map app I opened only cared about the fastest route.

Then I looked at the data. Pedestrian crashes in Atlanta aren't spread evenly. They pile up on a small share of streets, and the risk changes with the hour and the weather. So I set out to build what I wanted to use: a map that shows where and when traffic risk is highest, and a route that trades a few extra minutes for a lot less exposure.

## What it does

You open pathpro.tech on your phone. There's no app to install and no account. Tap "Where to?", pick a place, and PathPro starts from your location. The route card says something like "23 min, 54% less traffic risk, 4 min longer than the fastest route." Tap Start and it walks with you, speaking up before high-risk crossings so you can keep your eyes on the street.

![Route comparison on a phone](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/02-phone-route-comparison.png)
*The PathPro route (teal) next to the fastest one: 4 more minutes, 54% less traffic risk.*

![Walking navigation alert](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/03-phone-navigation-alert.png)
*During the walk, PathPro calls out high-risk stretches before you reach them.*

It also handles bikes, e-bikes, and scooters, because walking across Atlanta isn't realistic. Georgia Tech to Inman Park by bike at 9 PM comes out 72% lower-risk for about 4 extra minutes. On long walks it points you to the nearest MARTA station instead. I decided not to route cars: sending drivers down quieter streets just moves traffic onto the streets people walk on.

Tap any street to see why it scores the way it does. The factor bars add up exactly to the score, a chart shows when crashes happened there by hour, and there's a short explanation you can listen to.

![Risk Tides on desktop](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/04-desktop-risk-tides-home.png)
*Risk Tides: traffic risk across Atlanta, hour by hour, dry or wet.*

![Why this street scores high](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/05-desktop-route-explanation.png)
*The "Why?" view: factor bars that add up to the score, and a plain-language explanation.*

A few more things I built because people asked for them:

- A "well-lit and busier" option for walking after dark, and help points on the map: Georgia Tech's 100 blue-light phones, police, fire, hospitals, and MARTA.
- Share my walk, so a friend can follow along, and a check-in if you're running late, with 911 one tap away.
- Routines that stay on your phone. After a couple of walks it will ask "Heading back to Klaus?"
- Street reports (blocked sidewalk, signal out, flooding) that stay up for 14 days.
- Ask PathPro, an agent you can open from the map. Ask anything about the street, route or area you're looking at, and it answers from my model's own documents and that street's evidence, with every answer checked the same way as the explanations. Turn on memory and it remembers how you like to travel (never where you go); tap Forget me and it's gone.
- For city planners: tap "Imagine this street redesigned" and Grok Imagine draws what that street could look like with crosswalks, curb extensions, or better lighting. Gemini looks at the picture before it's shown, to confirm it shows the planned fixes and nothing it shouldn't.

![Share my walk](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/08-share-my-walk-follow.png)
*Share my walk: a friend follows your walk live from a link.*

## Does it actually work?

I trained on 2020–2023 and tested on 2024, a year the model never saw. The 10% of street length PathPro ranks highest had 74.3% of the 2024 pedestrian crashes (95% CI 70.5–78.3%). The City's High Injury Network, the list Atlanta uses to prioritize street fixes, caught 53.8%. Past crash counts alone caught 49.8%, and a random pick caught 11.9%. For cyclists it got 69.9%, against 43.6% for the High Injury Network.

Put another way: if a city spends the same budget fixing 10% of its street length, PathPro's ranking reaches about 38% more of next year's pedestrian crashes. For someone walking home, 4 extra minutes cuts their traffic-risk exposure by more than half.

## How I built it

I pulled about 250,000 public crash records from eight sources (ARC, the City of Atlanta, Central Atlanta Progress, and Georgia Tech), merged the duplicates, removed personal fields, and matched each crash to an OpenStreetMap street. One source turned out to store local time as UTC. I only caught it because its daylight/dark field didn't line up with the hour; fixing it took agreement from 60% to 94%.

![Data pipeline](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/technical/img/d1_pipeline.png)
*From public crash records to the model bundle the app serves.*

The model predicts crashes per street while accounting for how many people actually walk there. It's a Poisson GLM plus a monotone LightGBM, validated with spatial blocks, then blended with each street's own history using Empirical Bayes. A second model handles hour, day, darkness, and rain. I used no demographic or income data anywhere.

The AI features sit on top of the model; they don't replace it. Grok writes the "Why?" text from the street's own evidence, and a validator throws out any sentence containing a number that isn't in that evidence, so the score always comes from the model. Grok Voice reads the navigation alerts (the clips are fetched when you start walking, so they play instantly), and Grok Imagine draws the redesigns. If a provider is down, explanations fall back to Groq, then Gemini, then a plain template, and the voice falls back to ElevenLabs and then the phone's built-in voice.

The rest of the stack:

- Vultr runs the whole app on one VM in Atlanta, behind Caddy for HTTPS. One script deploys it.
- Backboard runs Ask PathPro: retrieval over the model card and docs, the on-screen context, and opt-in memory, with one private assistant per browser that Forget me deletes.
- The domain is pathpro.tech. Say it out loud: "path protect."
- Tiger Data (TimescaleDB + PostGIS) holds 220,594 crash rows and powers each street's crashes-by-hour chart through a continuous aggregate.
- MongoDB Atlas stores street reports and shared walks, with TTL indexes so old ones clean themselves up.
- The frontend is React, TypeScript, MapLibre, and deck.gl. Routing is Dijkstra on a SciPy sparse graph, about 150 ms at the median for both routes.

![Crashes by hour from Tiger Data](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/tiger-hourly.png)
*When crashes happened on a street, served from a Tiger Data continuous aggregate.*

I wrote tests before code the whole way through (about 1,145 of them) and ran separate review passes for the code, the ML, and security.

## Safety data, handled carefully

Adding crime data was the hardest call I made. Crime maps have a history of branding whole neighborhoods, and I didn't want to build another one. So PathPro only shows Atlanta Police reports of crimes against persons, grouped into hexagons by time of day, with no addresses or victim details, and always next to a note about what the data can and can't tell you. The bands adjust for how many people walk there, so an area with no reports never shows up as "higher." Crime never affects routing: a test multiplies every crime count by 1,000 and checks that the routes don't change.

![Safety layer with fairness note](https://raw.githubusercontent.com/ShaikNagurShareef/PathPro/main/docs/images/gallery/06-personal-safety-fairness-help-points.png)
*Reported crimes against persons by area and time of day, help points, and the fairness note that always sits beside them.*

Lighting data covers only about 4% of streets. Where the data doesn't know, PathPro says so.

## Challenges I ran into

- A third of the crashes wouldn't match any street. Midtown's sidewalks are mapped as separate lines from the roads, so I moved the model onto road centerlines and let the sidewalks inherit the risk. Matches went from 66% to 96%.
- A mentor tried my first version on their phone and told me it wasn't intuitive. They were right. I rebuilt the interface that afternoon around GPS, a simple route card, and turn-by-turn walking.
- My routes looked like zigzags. OSMnx stores many street geometries backwards, so I was drawing every other segment in reverse and overstating distance by 1.6×. It's fixed, and a test guards it now.
- My first confidence intervals were too narrow. Resampling by spatial block fixed that. I also found that rain matters less than I expected, and I report it.

## What I'm proud of

The model beats the City's own High Injury Network on a year it never saw. Every number on the screen traces back to the model, and the AI can't make one up. The safety features help without steering anyone away from a neighborhood. And the app keeps working when the weather API, an AI provider, a database, GPS, or the Wi-Fi goes down.

## What I learned

Most of the work was cleaning data and checking my own numbers, not picking a model. Crash data and crime data are both skewed by how many people are around to be counted, and saying that out loud made my claims stronger. Watching one person use the app on a real phone taught me more than any test did.

## What's next for PathPro

Wheelchair and stroller routing, better lighting data through the City or Georgia Power, a planning dashboard that pairs the top-ranked streets with Grok Imagine redesigns, and other cities, which mostly means swapping one boundary file.
```

## 5. Built with (tags)

(Devpost allows 25) python, fastapi, react, typescript, maplibre, deck.gl, lightgbm, scikit-learn, statsmodels, osmnx, geopandas, grok, grok-imagine, grok-voice, xai, gemini, groq, elevenlabs, timescaledb, postgis, tiger-data, mongodb-atlas, vultr, playwright, cursor

(As entered. If Backboard goes live, swap `cursor` or `statsmodels` for `backboard` to stay within 25.)

## 6. "Try it out" links

- https://pathpro.tech
- https://pathpro.tech/?demo=1 (offline demo)
- https://github.com/ShaikNagurShareef/PathPro

## 7. Video demo link

The YouTube URL of `media/pathpro_demo_v3.mp4` (3:02, Grok Voice narration). A compact copy also plays in the GitHub README.

## 8. Image gallery (upload in this order; the caption is the first line)

1. `docs/images/gallery/02-phone-route-comparison.png`: "Two taps to a lower-risk route: +4 min, 54% less traffic risk"
2. Grok Imagine redesign, a screenshot of the street sheet with the image and the "Checked by Gemini" line ⚑ (take it after the deploy)
3. Ask PathPro answering "Ask about this street", with its sources line ◇ (take it after the deploy)
4. `docs/images/gallery/03-phone-navigation-alert.png`: "Walking navigation with spoken high-traffic-risk callouts"
5. `docs/images/gallery/04-desktop-risk-tides-home.png`: "Risk Tides: traffic risk hour by hour across Atlanta"
6. `docs/images/gallery/05-desktop-route-explanation.png`: "Why? Factor bars that add up exactly, plus a grounded explanation"
7. `docs/images/gallery/06-personal-safety-fairness-help-points.png`: "Safety context with a fairness note, never used to route"
8. `docs/images/gallery/tiger-hourly.png`: "When crashes happened here, from a Tiger Data continuous aggregate"
9. `docs/images/gallery/08-share-my-walk-follow.png`: "Share my walk: a friend follows along live"
10. `docs/images/gallery/01-phone-home-routine-suggestion.png`: "Learns your routine, on your phone only"
11. `docs/images/gallery/07-city-pulse-area-score-live.png`: "City Pulse: area scores for all 3,537 hexes"

## 9. Submission form questions (as entered)

- **Schools:** Georgia State University
- **General track (one):** Oracle of the Deep - ML/AI
- **Sponsor track 1:** Aramco - A Marina's Mission
- **Sponsor track 2:** SpaceXAI - Make it Legendary ⚑ (the form allows only two sponsor tracks; Notability's prize is "Best Use of Notability", which PathPro doesn't use)
- **MLH prizes (ticked):** Best use of ElevenLabs, Gemini API (Gemini project number 1091754630519, submitted on the form), TigerData, Vultr, MongoDB Atlas. The .tech prize is entered through the domain question.
- **MLH prize to tick after deploy:** Backboard ◇ (Ask PathPro).
- **AI tools this weekend (shown in the gallery):** OpenAI (gpt-oss via Groq), Anthropic, Gemini, ElevenLabs, Other (xAI Grok, Cursor)
- **AI tools used:** AI coding assistants (Claude Code, Cursor) during development; Grok models, Grok Imagine, Grok Voice, Gemini and Backboard in the product. I followed a test-first workflow with independent review; scope, product decisions (including the safety layer and its safeguards), and review were mine.
- **Domain (.tech):** pathpro.tech
- **Data credits:** crash data from ARC, the City of Atlanta, Central Atlanta Progress, and Georgia Tech open data; Atlanta Police open data; OpenStreetMap contributors. The full list is in the README and `docs/safety_sources.md`.

## 10. After submitting

- Deploy, verify Grok, the Gemini check, and Ask PathPro on pathpro.tech, then remove the ⚑ and ◇ markers (or the lines) and tick the Backboard prize.
- Paste the Devpost link at expo.hexlabs.org.
- Notability: attach `docs/process/process_notes.pdf` per the sponsor's instructions.
