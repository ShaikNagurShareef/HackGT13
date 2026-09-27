# Judge Q&A cheat sheet

**Isn't this just "busy streets are risky"?**
Partly, and I say so. It's called exposure bias.
- Pedestrian activity (StreetLight) and traffic volume (AADT) are model features.
- The model beats plain past-crash ranking on two separate future years (2023: +22.6 points, 2024: +24.5 points, 95% CI +20 to +29).
- It beats the City's High Injury Network (74% vs 54% of next-year crashes in the top 10% of street length).
- The score means "where and when crashes concentrate", not "your personal odds".

**Why not crime?**
- Different problem, different data, different harms: crime maps stigmatize neighborhoods.
- The traffic-risk model uses zero demographic, income, race, or crime features. ARC's income, race, and EJ flags were deliberately removed.

**How do you know it isn't overfit?**
- **Temporal holdout:** trained on 2020–23, tested on 2024; also trained on 2020–22, tested on 2023.
- **Spatial-block cross-validation** for tuning.
- **Block-bootstrap confidence intervals.**
- **Leakage checks:** vehicle-crash density and neighborhood history only use training years. An independent ML review found no leakage.
- **Caveat:** I did look at 2024 during development, so 2023 is the cleaner second check.

**What does the AI actually do?**
- **Explanations:** one to three sentences written from a JSON of numbers the model produced. The explanation model never sees user text.
- Any sentence with an unsupported number, a banned word, or truncated output is replaced by a template.
- The risk score itself comes from the statistical model. The LLM never produces a number.
- **Voice** reads text the server already validated. **Grok Imagine** draws an illustration and **Ask PathPro** answers questions (both below); neither changes a score or a route.

**Why Grok first, then Groq?**
Grok writes the explanations when it's available (SpaceXAI track). Groq is next because it's fast: explanations must appear in under 3 seconds on a phone. Gemini is third, then a deterministic template. All four go through the same validator, so switching providers can't change what's allowed on screen.

**Why does Gemini check Grok's images?**
- An image model can add things nobody asked for: readable signs, brand logos, or faces that look like real people. On a civic planning tool, that would be misleading.
- Before an illustration is cached or shown, Gemini sees it next to the server's list of planned fixes. The card then says which fixes it shows ("Checked by Gemini: shows N of M planned fixes").
- An image with readable text, logos, or identifiable faces is never shown or cached. Grok gets one more try; if that is flagged too, the planner sees a friendly retry message.
- Gemini's answer is parsed strictly and can only confirm fixes that were actually planned. If Gemini can't be reached, the image is shown without the check line rather than blocked.
- The prompt Grok receives is built on the server from the street's modeled risk factors and road class. It never contains user text or street names, and every image is labeled "not a real photo".

**What does Ask PathPro remember about me?**
- **Nothing, by default.** Public questions go to a shared assistant with read-only memory, so no visitor can change what it knows.
- **Memory is opt-in** ("Remember my preferences"). Turning it on creates a private copy of the assistant for that browser only; the browser keeps just a signed token.
- It keeps **only stated travel preferences** (for example, "I usually walk home around 10 PM"). It never keeps places, streets, or routes.
- Questions asked about a street, route, or area on screen can read memory but **never write it**. Coordinates and your on-device walk routines are never sent to Backboard.
- **"Forget me"** deletes the private assistant and everything it remembered.
- Each visitor can ask 20 questions a day.

**How do Ask PathPro's answers avoid invented numbers?**
- The assistant answers from PathPro's curated docs (model card, metrics, safety sources, decision log, data and models, and this Q&A), plus server-built evidence for the street, route, or area on screen.
- Before an answer is shown, a validator checks that **every number in it appears in those docs or in that evidence**. It also rejects banned words, crime framing, off-topic answers, and links to anything other than PathPro's own docs.
- Anything that fails, and any timeout or upstream error, is replaced with a fixed pointer to the model card. The raw LLM text is never shown or logged.
- Street names come from OpenStreetMap, which anyone can edit, so they are flattened to one short line before they reach any LLM.

**Where's Tiger Data used?**
- Crash hypertable
- Hourly continuous aggregate behind "when crashes happened here"
- PostGIS street geometry
- A versioned risk grid

The demo never depends on the database: it has tight timeouts and the chart hides if the DB is down.

**Why is rain such a modest effect?**
- It is in Atlanta's data: wet pavement is about ×1.12 for pedestrian crashes; darkness about ×1.6.
- Rain also keeps people indoors, so fewer pedestrians are exposed.
- On held-out data, light and rain add a small but real gain (+1.3% deviance) beyond a smoothed hour × day baseline. I report it at that size.

**How accurate is the route claim?**
- "54% less exposure" = expected crashes along the path (risk density × length), re-scored at the time you'd actually walk each street.
- The detour budget is capped at min(1.25× the fastest time, +6 min).

**What's the data?**
- About 250k public crash records from the Atlanta Regional Commission, City of Atlanta, Central Atlanta Progress, and Georgia Tech, 2013–2026.
- Merged across sources.
- 95% of pedestrian crashes snapped to streets (2,228 in 2020–24 across the city).
- Personal fields in the raw data are dropped at ingest.

**Is everything on the Devpost live?**
The map, routing, explanations (Groq → Gemini → template), ElevenLabs voice, Tiger Data, MongoDB Atlas, and the Vultr deploy are live on pathpro.tech. The Grok features, the Gemini image check, and Ask PathPro are built and tested, and were verified against the real APIs locally, but they are not deployed yet. The Devpost write-up only calls them live once they are.

**Why a solo build?**
I entered HackGT 13 on my own, under the team name Coding Claws, from Georgia State University. Working alone meant keeping scope honest: test-first commits, independent review passes for the ML, security, and code, and an offline demo mode so one person can run the expo table. Earlier docs and the v2 video listed a four-person team; that was wrong, and the record is corrected in the decision log.

**What's next?**
- Wheelchair and stroller profiles
- Exposure-normalized "per trip" risk
- A campus/city dashboard for planners (Vision Zero), paired with Grok Imagine redesigns
- Live near-miss reports
- More cities: the coverage area is one config polygon

**Did you use AI to build it?**
Yes, disclosed. AI coding assistants were used during development, with a test-first workflow and independent ML and security review; the Devpost write-up lists the tools. The scope, product decisions, and review were mine.
