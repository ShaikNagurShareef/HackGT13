# Devpost gallery

Eight 1600×1000 app images plus one Tiger Data chart, in upload order. The app screens were captured with Playwright from the offline demo at https://pathpro.tech/?demo=1 (deterministic: Klaus → Midtown MARTA, Friday 10:30 PM, wet). The exception is `07`, which comes from the live site. Phone shots are Pixel 7 captures (1082×2202) framed onto 1600×1000. Nothing was created on the production server.

| File | Devpost caption |
| --- | --- |
| `01-phone-home-routine-suggestion.png` | Map-first home: one "Where to?" pill, and your usual walk (learned on the device only) is one tap away. |
| `02-phone-route-comparison.png` | Fastest vs PathPro route: +4 min for 54% less traffic-risk exposure, with Start, Listen, Why? and Share. |
| `03-phone-navigation-alert.png` | Walking navigation warns before the high-traffic-risk stretch; without GPS it previews the walk. |
| `04-desktop-risk-tides-home.png` | Desktop: a persistent sidebar, with Risk Tides re-coloring about 50,000 Atlanta street segments by hour, day and weather. |
| `05-desktop-route-explanation.png` | Why this route: a grounded explanation, the high-risk stretches it avoids, and the stretch both routes share. |
| `06-personal-safety-fairness-help-points.png` | Personal-safety mode: help points and reported crimes against persons, always with the fairness note. Crime never chooses routes. |
| `07-city-pulse-area-score-live.png` | City Pulse (live site): area traffic-risk scores for all 3,537 hexes of the City of Atlanta, with the factors behind one area's score. |
| `08-share-my-walk-follow.png` | Share my walk: a live link a friend can follow, which expires 6 hours after the last update. The follow page shows a sample walk served in the browser. |
| `09-ask-pathpro-street.png` | Ask PathPro about the street on screen (Fifth Street NW, 9 PM): the answer lists the same factors as the score bars. |
| `10-ask-pathpro-memory.png` | Ask PathPro from Map options, with the opt-in "Remember my preferences" switch (off) and its privacy note. |
| `11-imagine-street-redesign.png` | Imagine this street redesigned: a Grok Imagine illustration of evidence-based fixes, labeled "not a real photo", with the Gemini check line. |
| `12-route-ask.png` | Desktop: Ask about this route. The answer names the stretches the route avoided, matching the route explanation. |
| `tiger-hourly.png` | Tiger Data: when Atlanta crashes happen, by hour, summed from the `crashes_hourly` continuous aggregate over the crash hypertable (57 chunks, 220,594 rows). |

## How these were made

- **App screens.** A Playwright script drove the real UI with role-based selectors, for example `getByRole('button', { name: 'Start', exact: true })`.
  - The routine card in `01` comes from four sample walks seeded into the browser's local storage. That is where PathPro keeps routines.
  - The "Sharing live" state in `08` is the demo's on-device simulation.
  - The follow page in `08` is fed a sample walk by intercepting its `GET /api/walks/…` request inside the browser, so no walk exists on the server.
- **Tiger chart.** A Python script queried the Tiger Data service read-only: hypertable chunk count, row counts, and the hour-of-day profile from `crashes_hourly` in Atlanta local time. Matplotlib rendered the chart. Counts are weighted sums, because an intersection crash is split across its approaches.
- **Ask and Imagine screens (`09`–`12`).** Playwright against the app running locally with real Backboard, Grok and Gemini calls. Location permission was never granted and memory stayed off. The Gemini line in `11` comes from a real Gemini check of that picture, run with a longer timeout after the in-app check timed out.
