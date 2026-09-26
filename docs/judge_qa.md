# Judge Q&A cheat sheet

**Isn't this just "busy streets are risky"?**
Partly, and we say so. It's called exposure bias.
- We include pedestrian activity (StreetLight) and traffic volume (AADT) as features.
- The model beats plain past-crash ranking on two separate future years (2023: +22.6 points, 2024: +24.5 points, 95% CI +20 to +29).
- It beats the City's High Injury Network (74% vs 54% of next-year crashes in the top 10% of street length).
- The score means "where and when crashes concentrate", not "your personal odds".

**Why not crime?**
- Different problem, different data, different harms: crime maps stigmatize neighborhoods.
- We use zero demographic, income, race, or crime features. ARC's income, race, and EJ flags were deliberately removed.

**How do you know it isn't overfit?**
- **Temporal holdout:** trained on 2020–23, tested on 2024; also trained on 2020–22, tested on 2023.
- **Spatial-block cross-validation** for tuning.
- **Block-bootstrap confidence intervals.**
- **Leakage checks:** vehicle-crash density and neighborhood history only use training years. An independent ML review found no leakage.
- **Caveat:** we did look at 2024 during development, so 2023 is the cleaner second check.

**What does the AI actually do?**
- It writes one to three sentences from a JSON of numbers the model produced.
- It never sees user text.
- Any sentence with an unsupported number, a banned word, or truncated output is replaced by a template.
- The risk score itself comes from the statistical model. The LLM never produces a number.

**Why Groq?**
Speed. Explanations must appear in under 3 seconds on a phone. Gemini is the fallback, then a template.

**Where's Tiger Data used?**
- Crash hypertable
- Hourly continuous aggregate behind "when crashes happened here"
- PostGIS street geometry
- A versioned risk grid

The demo never depends on the database: it has tight timeouts and the chart hides if the DB is down.

**Why is rain such a modest effect?**
- It is in Atlanta's data: wet pavement is about ×1.12 for pedestrian crashes; darkness about ×1.6.
- Rain also keeps people indoors, so fewer pedestrians are exposed.
- On held-out data, light and rain add a small but real gain (+1.3% deviance) beyond a smoothed hour × day baseline. We report it at that size.

**How accurate is the route claim?**
- "54% less exposure" = expected crashes along the path (risk density × length), re-scored at the time you'd actually walk each street.
- The detour budget is capped at min(1.25× the fastest time, +6 min).

**What's the data?**
- About 250k public crash records from the Atlanta Regional Commission, City of Atlanta, Central Atlanta Progress, and Georgia Tech, 2013–2026.
- Merged across sources.
- 95% of pedestrian crashes snapped to streets (2,228 in 2020–24 across the city).
- Personal fields in the raw data are dropped at ingest.

**What's next?**
- Cycling and wheelchair profiles
- Exposure-normalized "per trip" risk
- A campus/city dashboard for planners (Vision Zero)
- Live near-miss reports
- More cities: the coverage area is one config polygon

**Did you use AI to build it?**
Yes, disclosed. The code was written with Claude Code using the ECC workflow: test-first, with independent ML and security review agents. The scope, product decisions, and review were ours.
