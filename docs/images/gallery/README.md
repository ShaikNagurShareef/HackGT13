# Devpost gallery

Thirteen app images plus one Tiger Data chart, in upload order. `01`–`08` and `13` are 1600×1000; `09`–`11` are 390×844 phone captures at 2× (780×1688) and `12` is a 1440×900 desktop capture. Framed phone shots are Pixel 7 captures (1082×2202) placed on a 1600×1000 card. Nothing was created on the production server: no street reports, no shared walks, and no new street illustrations.

**UI refresh (26 September 2026).** `02`, `04` and `09`–`13` were retaken from the live site at https://pathpro.tech after the UI refresh: the round Ask PathPro agent button on the map, the chat-style Ask panel, the "Ask about this street / route / area" pills, and the segmented travel-mode control. `02` still uses the offline demo (https://pathpro.tech/?demo=1, deterministic: Klaus → Midtown MARTA, Friday 10:30 PM, wet), served from the live site. `01`, `03` and `05`–`08` are from the earlier capture and predate the refresh.

| File | Devpost caption |
| --- | --- |
| `01-phone-home-routine-suggestion.png` | Map-first home: one "Where to?" pill, and your usual walk (learned on the device only) is one tap away. |
| `02-phone-route-comparison.png` | Fastest vs PathPro route: +4 min for 54% less traffic-risk exposure, with the Walk · Bike · E-bike · Scooter mode control and Start, Listen, Why? and Share. |
| `03-phone-navigation-alert.png` | Walking navigation warns before the high-traffic-risk stretch; without GPS it previews the walk. |
| `04-desktop-risk-tides-home.png` | Desktop: a persistent sidebar, with Risk Tides re-coloring about 50,000 Atlanta street segments by hour, day and weather, and the Ask PathPro agent button above the zoom buttons. |
| `05-desktop-route-explanation.png` | Why this route: a grounded explanation, the high-risk stretches it avoids, and the stretch both routes share. |
| `06-personal-safety-fairness-help-points.png` | Personal-safety mode: help points and reported crimes against persons, always with the fairness note. Crime never chooses routes. |
| `07-city-pulse-area-score-live.png` | City Pulse (live site): area traffic-risk scores for all 3,537 hexes of the City of Atlanta, with the factors behind one area's score. |
| `08-share-my-walk-follow.png` | Share my walk: a live link a friend can follow, which expires 6 hours after the last update. The follow page shows a sample walk served in the browser. |
| `09-ask-pathpro-street.png` | Ask about this street (Fifth Street NW, 9 PM), in the chat panel: the context pill, your question in a teal bubble, and an answer that lists the same factors as the score bars. |
| `10-ask-pathpro-memory.png` | Ask PathPro opened from the agent button: a general answer, suggestion chips, the round Send button, and the opt-in "Remember my preferences" switch (off) with its privacy note. |
| `11-imagine-street-redesign.png` | Imagine this street redesigned (10th Street NW): a Grok Imagine illustration of evidence-based fixes, labeled "not a real photo", with the "Checked by Gemini" line. |
| `12-route-ask.png` | Desktop: Ask about this route, answered in the docked chat card. The answer names the stretches the route avoided, matching the route explanation. |
| `13-agent-button.png` | Ask PathPro is one tap away: the round agent button sits on the phone map, above the layers and locate buttons. |
| `tiger-hourly.png` | Tiger Data: when Atlanta crashes happen, by hour, summed from the `crashes_hourly` continuous aggregate over the crash hypertable (57 chunks, 220,594 rows). |

## How these were made

- **App screens.** A Playwright script drove the real UI with role-based selectors, for example `getByRole('button', { name: 'Start', exact: true })`.
  - The routine card in `01` comes from four sample walks seeded into the browser's local storage. That is where PathPro keeps routines.
  - The "Sharing live" state in `08` is the demo's on-device simulation.
  - The follow page in `08` is fed a sample walk by intercepting its `GET /api/walks/…` request inside the browser, so no walk exists on the server.
- **Tiger chart.** A Python script queried the Tiger Data service read-only: hypertable chunk count, row counts, and the hour-of-day profile from `crashes_hourly` in Atlanta local time. Matplotlib rendered the chart. Counts are weighted sums, because an intersection crash is split across its approaches.
- **Refreshed screens (`02`, `04`, `09`–`13`).** Playwright (headless Chromium) against the live site, https://pathpro.tech, with real Backboard answers. A request filter in the script let through only reads, route and explanation requests, Ask questions, and the Imagine request for streets that already had a cached picture. Everything else, including street reports, shared walks and Ask memory, was blocked. Location permission was never granted, and "Remember my preferences" stayed off (`10` opens only its info note). `11` loads the cached, Gemini-checked picture for 10th Street NW, so no new picture was generated. `02` and `13` are Pixel 7 captures placed on a 1600×1000 card.
