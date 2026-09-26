# PathPro API reference

Derived from `backend/app/api/*.py`, `backend/app/api/schemas.py`, `backend/app/api/walk_schemas.py`, and the services they call. Sample responses are trimmed copies of real responses (recorded demo fixtures in `frontend/public/demo/fixtures.json`, or read-only calls to the live site).

## Base URLs

| Environment | Base URL | Notes |
| --- | --- | --- |
| Production | `https://pathpro.tech/api` | Caddy strips `/api` and proxies to uvicorn on `127.0.0.1:8000`. Also `https://www.pathpro.tech/api` and `https://155-138-233-35.sslip.io/api`. |
| Local API | `http://127.0.0.1:8000` | `cd backend && uv run uvicorn app.main:create_app --factory --reload`. No `/api` prefix. |
| Local SPA | `http://127.0.0.1:5173/api` | Vite dev proxy rewrites `/api/*` to the local API. |

Paths below are written without the `/api` prefix. FastAPI's generated OpenAPI document is served at `/openapi.json` (production: `https://pathpro.tech/api/openapi.json`). The interactive `/docs` page loads Swagger UI from a CDN, which the production CSP blocks, so use it locally.

## Conventions

### Response envelope

Every JSON endpoint returns the same envelope (`api/envelope.py`):

```json
{ "success": true, "data": { "...": "..." }, "error": null, "model_version": "pp-20260926-1902-f49c0d2" }
```

```json
{ "success": false, "data": null,
  "error": { "code": "OUT_OF_COVERAGE", "message": "PathPro covers the City of Atlanta for now. Pick a starting point and destination inside city limits." },
  "model_version": "pp-20260926-1902-f49c0d2" }
```

- `error.code` is stable and machine-readable; `error.message` is user-facing copy.
- Request-validation failures (bad JSON, wrong types, values outside limits, unknown fields where forbidden) return **422** with code `BAD_REQUEST` and the message "That request was not valid." Validator details are never echoed.
- Unhandled exceptions return **500** `INTERNAL` "Something went wrong. Please retry." with no stack trace.
- Exceptions: `POST /tts` returns raw `audio/mpeg` on success; unknown paths and wrong methods get FastAPI's default `{"detail": "Not Found"}` (404) and `{"detail": "Method Not Allowed"}` (405).
- Responses are typed with pydantic response models; the SPA validates every body with zod (`frontend/src/api/schemas.ts`).

### Time and condition parameters

| Parameter | Type | Accepted values |
| --- | --- | --- |
| `t` / `depart_at` | string, max 40 chars | `now`, `+Nm` or `+Nh` (N up to 3 digits), or ISO-8601. Naive ISO is Atlanta wall-clock time. Must be within 400 days of now. Invalid → 422 `BAD_TIME` (segments, areas, explain) or `BAD_DEPARTURE` (routes). |
| `cond` | enum | `live` (Open-Meteo forecast for that hour), `dry`, `wet` (override). Default `live`. |
| `mode` | enum | `walk`, `bike`, `ebike`, `scooter`. Default `walk`. Ride modes need the ride model (else 503 `MODE_UNAVAILABLE`). |

`condition_used` in responses: `{cond: "dry"|"wet", source: "live"|"override"|"assumed", label}`. `assumed` means the forecast was unavailable and dry was used.

### Rate limits

Implemented in `app/middleware.py` as a per-client sliding 60-second window. The client key is `request.client.host`, which uvicorn sets from Caddy's `X-Forwarded-For` only because `--forwarded-allow-ips 127.0.0.1` trusts the local proxy; IPv6 addresses are grouped by /64.

| Class | Default limit | Env var | Applies to |
| --- | --- | --- | --- |
| Exempt | none | n/a | Paths starting `/healthz`, `/static` |
| General | 300 requests / min / client | `RATE_LIMIT_PER_MINUTE` | Every other request, including all reads, `POST /routes`, and `PUT /walks/{id}/position` |
| Paid / write | 30 requests / min / client, **in addition to** the general limit | `PAID_RATE_LIMIT_PER_MINUTE` | Any method on `/explain`, `/geocode`, `/tts`; `POST /reports`; `POST /walks` |

Over either limit → **429** `RATE_LIMITED` "Too many requests. Try again in a minute." (envelope with `model_version: null`).

Why `PUT /walks/{id}/position` is on the general limit: at the expo every visitor shares the venue's NAT address, and each walker posts about 12 updates per minute. On the paid limit, three walkers would exhaust it for the whole hall. Instead an in-memory per-walk gate rejects updates that arrive within 3 seconds of the last accepted one (429 `WALK_THROTTLED`) before any database read.

Daily budgets (per process, reset at local midnight) cap spend independently of the per-client limits: LLM generations `LLM_DAILY_BUDGET` (3,000), Geoapify calls `GEOCODE_DAILY_BUDGET` (2,500), ElevenLabs calls `TTS_DAILY_BUDGET` (500). Past a budget the endpoint degrades (template text, empty results, device voice) instead of failing.

### CORS

`CORSMiddleware` with `allow_origins` from `ALLOWED_ORIGINS` (comma-separated), methods `GET, POST, PUT`, header `Content-Type`, `allow_credentials=False`. `deploy/deploy.sh` sets the origins to `https://` plus each Caddy site name (`pathpro.tech`, `www.pathpro.tech`, `155-138-233-35.sslip.io`). Preflights from other origins get 400. The SPA itself is same-origin, so CORS matters only to third-party callers.

### Endpoint summary

| Method | Path | Rate class | Purpose |
| --- | --- | --- | --- |
| GET | `/healthz` | exempt | Liveness and dependency status |
| GET | `/meta` | general | Model version, coverage, frames layout, modes, headline metrics |
| POST | `/routes` | general | Fastest vs lower-risk route |
| GET | `/segments/{seg_id}` | general | Street score, factors, history |
| GET | `/segments/{seg_id}/hourly` | general | Crashes by hour from Tiger Data |
| GET | `/segments/{seg_id}/reports` | general | Community reports on a street |
| POST | `/explain` | paid | One-to-three-sentence grounded explanation |
| POST | `/tts` | paid | MP3 of the server's explanation |
| GET | `/geocode` | paid | Address autocomplete |
| GET | `/conditions/live` | general | Current dry/wet condition |
| GET | `/areas/lookup` | general | City Pulse score at a point |
| GET | `/areas/{cell}` | general | City Pulse score for an H3 cell |
| POST | `/reports` | paid | Flag a traffic-related street issue |
| GET | `/reports` | general | Reports in a map viewport |
| GET | `/reports/summary` | general | Active reports per category |
| POST | `/walks` | paid | Start sharing a walk |
| PUT | `/walks/{walk_id}/position` | general + per-walk gate | Owner position update |
| GET | `/walks/{walk_id}` | general | What a follower sees |
| GET | `/safety/meta` | general | Safety-layer sources and day parts |
| GET | `/safety/hexes` | general | Safety hexes in a viewport for a day part |
| GET | `/safety/help-points` | general | Help points in a viewport |
| GET | `/transit/stations` | general | MARTA rail stations in coverage |
| GET | `/static/{model_version}/{file}` | exempt | Bundle files (served by Caddy from disk in production) |

---

## Health and metadata

### `GET /healthz`

No parameters. Pings Tiger Data (`SELECT 1`, 3 s connect, 800 ms statement) and MongoDB Atlas (`ping`) on every call.

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | `ok` \| `degraded` | `degraded` when `database` or `reports` is `unavailable` |
| `model_version` | string | Served walk bundle |
| `segments` | int | Walk segments (49,915) |
| `graph_nodes` | int | Walk graph nodes (84,758) |
| `database` | `ok` \| `unavailable` \| `not_configured` | Tiger Data |
| `reports` | `ok` \| `unavailable` \| `not_configured` | MongoDB Atlas |
| `safety` | `ok` \| `unavailable` | Personal-safety layer loaded |
| `modes` | `{walk: "ok", ride: "ok" \| "unavailable"}` | Ride model loaded |

```json
{"success":true,"data":{"status":"ok","model_version":"pp-20260926-1902-f49c0d2","segments":49915,"graph_nodes":84758,
 "database":"ok","reports":"ok","safety":"ok","modes":{"walk":"ok","ride":"ok"}},"error":null,"model_version":"pp-20260926-1902-f49c0d2"}
```

The endpoint always returns 200 while the process is up; read `status` for dependency health.

### `GET /meta`

No parameters.

| Field | Type | Meaning |
| --- | --- | --- |
| `model_version`, `data_through` | string | Bundle id; last crash date (2026-09-19) |
| `n_segments` | int | Walk segments |
| `coverage_bbox` | `[west, south, east, north]` | City of Atlanta bounds |
| `day_groups`, `conditions` | string[] | `weekday, friday, saturday, sunday`; `dry, wet` |
| `reference_dates` | `{day_group: date}` | Date each frame set was lit for |
| `frame_light` | `{day_group: [24 × "day"\|"twilight"\|"dark"]}` | Light per frame hour |
| `static_base` | string | `/static/{model_version}`; frames at `{static_base}/frames_{day}_{cond}.bin` |
| `headline` | object | Walk headline metrics (capture, CI, baselines, ROC-AUC, temporal gain) |
| `spatial_factors`, `temporal_factors` | `{key, label, points: 0}[]` | Factor keys and labels |
| `modes` | `{key, label, available, speed_kmh, network: "walk"\|"ride", static_prefix: ""\|"ride_"}[]` | Travel modes |
| `ride_model` | object \| null | Ride headline metrics |

```json
{"success":true,"data":{"model_version":"pp-20260926-1902-f49c0d2","data_through":"2026-09-19","n_segments":49915,
 "coverage_bbox":[-84.55085,33.64792,-84.28956,33.88682],"day_groups":["weekday","friday","saturday","sunday"],
 "conditions":["dry","wet"],"reference_dates":{"friday":"2026-09-25","saturday":"2026-09-26","sunday":"2026-09-27","weekday":"2026-09-28"},
 "static_base":"/static/pp-20260926-1902-f49c0d2",
 "modes":[{"key":"walk","label":"Walk","available":true,"speed_kmh":4.68,"network":"walk","static_prefix":""},
          {"key":"bike","label":"Bike","available":true,"speed_kmh":15.0,"network":"ride","static_prefix":"ride_"}, "..."],
 "headline":{"capture_top10":0.7433,"capture_top10_ci95":[0.7049,0.7827],"roc_auc":0.889, "...":"..."},
 "spatial_factors":[{"key":"history","label":"Pedestrian crash history here","points":0}, "..."]}, "error":null, "model_version":"..."}
```

---

## Routing

### `POST /routes`

Request body (`RouteRequest`):

| Field | Type | Limits / default |
| --- | --- | --- |
| `origin` | `{lat, lon}` | lat −90..90, lon −180..180; must be inside the City of Atlanta (city hexes) |
| `destination` | `{lat, lon}` | same |
| `depart_at` | string | default `now`; see time parameters |
| `cond` | `live`\|`dry`\|`wet` | default `live` |
| `prefer` | `lower_traffic_risk`\|`lit_and_busy` | default `lower_traffic_risk`; `lit_and_busy` changes walks after dark only and is ignored for ride modes |
| `mode` | `walk`\|`bike`\|`ebike`\|`scooter` | default `walk` |

Processing: coverage check → snap each end to the nearest graph node (≤ 150 m) → resolve condition → plan in a worker thread (see [architecture §6.1](architecture.md#61-plan-a-route)) → add community reports on the recommended walk route (≤ 0.5 s wait) → store the result under `route_key` for `/explain`.

Response `RoutesData`:

| Field | Type | Meaning |
| --- | --- | --- |
| `condition_used` | ConditionUsed | Dry/wet actually used |
| `depart_at` | ISO string | Resolved departure (Atlanta offset) |
| `fastest` | RouteOut | Fastest route, re-scored at traversal times |
| `pathpro` | RouteOut \| null | Lower-risk route, or null when the fastest already is |
| `message_code` | `ok` \| `tradeoff_exists` \| `fastest_is_lower_risk` \| `long_trip` | Drives the copy |
| `message` | string \| null | e.g. "The fastest route is already the lower-risk option." |
| `time_cost_min` | float \| null | Extra minutes for `pathpro` |
| `exposure_reduction_pct` | int \| null | Percent less expected-crash exposure (never ≤ 0) |
| `unavoidable` | string[] | High-risk streets both routes use |
| `avoided` | `{seg_id, name, score}[]` | High-risk streets (≥ 75) on the fastest route that `pathpro` avoids entirely |
| `route_key` | 16 hex chars | Key for `/explain` and `/tts` |
| `reports` | ReportOut[] | Community reports on the recommended route (walk only; context only) |
| `mode`, `prefer` | enums | Mode and the preference actually applied |

`RouteOut`: `coords` (`[lon, lat][]`, 6 decimals), `duration_s`, `distance_m`, `risk_score` (0–100, length-weighted), `band` (`Lower`/`Moderate`/`Elevated`/`High`), `exposure` (expected-crash exposure: Σ density per 100 m × length), `high_risk_m` (metres scoring ≥ 75), `limited_data_m`, `segment_ids`, `top_segments` (up to 3 named streets contributing most exposure), `alerts` (stretches ≥ 90 merged within 100 m: `start_m, end_m, names, score, stretches`), `safety` (walk only, else null: `lit_share`, `busy_share`, `help_points_within_100m`, `crimes_persons_nearby`, `day_part`).

Sample (Klaus Building → Midtown MARTA, Friday 22:30, `cond: "wet"`; coordinate and id arrays trimmed):

```json
{"success":true,"data":{
  "condition_used":{"cond":"wet","source":"override","label":"Wet (your choice)"},
  "depart_at":"2026-09-25T22:30:00-04:00",
  "fastest":{"coords":[[-84.39626,33.77705],"..."],"duration_s":1104.9,"distance_m":1436.3,"risk_score":98,"band":"High",
    "exposure":1.9257,"high_risk_m":1292.0,"limited_data_m":60.0,"segment_ids":[3723,3724,"..."],
    "top_segments":[{"seg_id":13343,"name":"Fifth Street Northwest","score":99},{"seg_id":14275,"name":"Peachtree Place Northwest","score":100}],
    "alerts":[{"start_m":89.0,"end_m":1372.0,"names":["Ferst Drive Northwest","..."],"score":100,"stretches":15}],
    "safety":{"lit_share":1.0,"busy_share":1.0,"help_points_within_100m":7,"crimes_persons_nearby":12,"day_part":"night"}},
  "pathpro":{"duration_s":1355.0,"distance_m":1761.5,"risk_score":93,"band":"High","exposure":0.8846,"...":"..."},
  "message_code":"tradeoff_exists",
  "message":"A lower-risk route exists but adds 12 min. Showing the best option under 6 extra min.",
  "time_cost_min":4.2,"exposure_reduction_pct":54,"unavoidable":["Fifth Street Northwest"],
  "avoided":[{"seg_id":18085,"name":"8th Street Northwest","score":97},{"seg_id":14275,"name":"Peachtree Place Northwest","score":100}],
  "route_key":"f5ae7c3aebe46e80","reports":[],"mode":"walk","prefer":"lower_traffic_risk"},
 "error":null,"model_version":"pp-20260926-1902-f49c0d2"}
```

Errors: 422 `BAD_REQUEST`, `BAD_DEPARTURE`, `OUT_OF_COVERAGE`, `SNAP_TOO_FAR` ("Move the pin closer to a sidewalk or street."), `TOO_CLOSE` (under 60 m), `NO_CONNECTION`; 503 `MODE_UNAVAILABLE`; 429 `RATE_LIMITED`.

---

## Street segments

### `GET /segments/{seg_id}`

| Parameter | In | Type | Default |
| --- | --- | --- | --- |
| `seg_id` | path | int (0 ≤ id < n_segments) | required |
| `t` | query | string ≤ 40 | `now` |
| `cond` | query | `live`\|`dry`\|`wet` | `live` |
| `mode` | query | ModeKey | `walk` (ride ids index the ride model; same ids) |

Response `SegmentDetail`: `seg_id`, `name`, `road_group` (`arterial`/`collector`/`local`), `score`, `band`, `confidence` (`high`/`medium`/`limited`), `baseline_points`, `factors` (top 5 `{key, label, points}`, signed), `remainder_points`, `history` (`crashes`, `ped_crashes`, `dark_share`, `wet_share`, `period: "2020-2024"`, `bike_crashes` for ride modes else null), `condition_used`, `at`, `mode`. Invariant: `baseline_points + Σ factors.points + remainder_points == score`.

```json
{"success":true,"data":{"seg_id":3722,"name":"Fowler Street Northwest","road_group":"local","score":92,"band":"High",
 "confidence":"medium","baseline_points":56,
 "factors":[{"key":"nearby_history","label":"Pedestrian crashes on nearby streets","points":19},
            {"key":"vehicle_crashes","label":"Vehicle crashes on this street","points":9},
            {"key":"intersection","label":"Intersection complexity","points":4},
            {"key":"length","label":"Block length","points":-3},
            {"key":"light","label":"Darkness","points":2}],
 "remainder_points":5,
 "history":{"crashes":5.2,"ped_crashes":0.8,"dark_share":0.068,"wet_share":0.227,"period":"2020-2024","bike_crashes":null},
 "condition_used":{"cond":"wet","source":"override","label":"Wet (your choice)"},"at":"2026-09-25T22:30:00-04:00","mode":"walk"},
 "error":null,"model_version":"pp-20260926-1902-f49c0d2"}
```

Errors: 404 `NOT_FOUND`; 422 `BAD_TIME`, `BAD_REQUEST`; 503 `MODE_UNAVAILABLE`.

### `GET /segments/{seg_id}/hourly`

`mode` query (default `walk`); only walk is supported. Reads `crashes_hourly` in Tiger Data and returns 24 weighted sums in Atlanta local hours.

```json
{"success":true,"data":{"seg_id":14275,"crashes":[0.0,"...",0.25,0.5,0.75,0.5],"ped_crashes":[0.0,"...",0.0,0.0,0.0,0.25],"source":"tiger_data"},
 "error":null,"model_version":"pp-20260926-1902-f49c0d2"}
```

(Arrays have 24 entries; weights are fractional because intersection crashes are split across approaches.) Errors: 404 `NOT_FOUND` (id out of range or `mode` not walk); 503 `HISTORY_UNAVAILABLE` (database unset, down, or slower than 800 ms).

### `GET /segments/{seg_id}/reports`

Active community reports on one walk segment, most-confirmed first (max 50). Response `ReportOut[]` (see reports). Errors: 404 `NOT_FOUND`; 503 `REPORTS_UNAVAILABLE`.

---

## Explanations and voice

### `POST /explain`

Body (`ExplainRequest`):

| Field | Type | Limits |
| --- | --- | --- |
| `kind` | `segment`\|`route` | required |
| `seg_id` | int ≥ 0 | required for `segment` |
| `route_key` | string `^[0-9a-f]{16}$` | required for `route`; must be in the server's recent-routes cache (512 entries) |
| `t` | string ≤ 40 | segment only, default `now` |
| `cond` | Condition | segment only, default `live` |
| `mode` | ModeKey | segment only, default `walk` |

Response: `{text, source}` where `source` ∈ `groq`, `groq-20b`, `gemini`, `template`, `cache`.

```json
{"success":true,"data":{"text":"The PathPro route adds 4.2 min and cuts traffic-risk exposure 54% by avoiding Peachtree Place Northwest and Williams Street Northwest. Both routes use Fifth Street Northwest, so stay alert there.","source":"template"},
 "error":null,"model_version":"pp-20260926-1902-f49c0d2"}
```

Guarantees: the text comes only from server-built evidence and passes the validator (≤ 3 sentences, ≤ 420 chars, every number and clock time present in the evidence, no banned framing); otherwise it is the deterministic template. Total LLM time budget 4 s (`EXPLAIN_BUDGET_S`), first provider 1.6 s (`GROQ_BUDGET_S`). Errors: 404 `ROUTE_EXPIRED`, `NOT_FOUND`; 422 `BAD_REQUEST`, `BAD_TIME`; 503 `MODE_UNAVAILABLE`; 429.

### `POST /tts`

Same body as `/explain`. The server produces (or reuses) its own explanation and sends that text to ElevenLabs (`eleven_flash_v2_5`, `mp3_44100_64`, 6 s timeout). Clients cannot supply text.

- 200: `audio/mpeg` body, `Cache-Control: no-store`.
- 503 `TTS_UNAVAILABLE` "Voice is unavailable; using the device voice." (no key or voice id, text over 420 chars, daily budget spent, or upstream error). The SPA then uses the browser's speech synthesis.

---

## Places and conditions

### `GET /geocode`

| Parameter | Type | Limits |
| --- | --- | --- |
| `q` | string | 1–80 chars (whitespace collapsed; fewer than 3 characters returns `[]`) |

Geoapify autocomplete filtered to the city rectangle and biased toward Georgia Tech, max 5 results, cached 1 h. The key stays on the server. Response `{label, address, lat, lon, in_coverage}[]`. Failures, missing key, or an exhausted budget return `[]`.

### `GET /conditions/live`

Response `ConditionUsed` for the current hour: `{"cond":"dry","source":"live","label":"Dry · live forecast"}`. Forecast cached 10 min; stale forecast used up to 1 h; otherwise `{"cond":"dry","source":"assumed","label":"Live weather unavailable — using dry conditions."}`. Freezing-precipitation and snow weather codes count as wet with the label "Icy conditions are rarer in our data — use extra caution."

---

## City Pulse

### `GET /areas/lookup`

| Parameter | Type | Limits |
| --- | --- | --- |
| `lat`, `lon` | float | −90..90, −180..180 |
| `t`, `cond` | as above | defaults `now`, `live` |

### `GET /areas/{cell}`

`cell` must match `^[0-9a-f]{15}$` (H3 resolution 9); `t`, `cond` as above.

Response `AreaDetail`: `cell`, `lat`, `lon`, `score`, `band`, `confidence`, `baseline_points`, `factors` (top 4, including `time_conditions`), `remainder_points`, `crashes`, `ped_crashes`, `period`, `in_street_coverage`, `condition_used`, `at`.

```json
{"success":true,"data":{"cell":"8944c1aaa2fffff","lat":33.754171,"lon":-84.41506,"score":95,"band":"High","confidence":"high",
 "baseline_points":57,"factors":[{"key":"vehicle_crashes","label":"Vehicle crashes in this area","points":30},
 {"key":"activity","label":"Pedestrian activity and transit","points":5},{"key":"nearby","label":"Pedestrian crashes in surrounding areas","points":2},
 {"key":"time_conditions","label":"Time of day and conditions","points":0}],"remainder_points":1,"crashes":115.0,"ped_crashes":1.0,
 "period":"2020-2024","in_street_coverage":true,"condition_used":{"cond":"wet","source":"override","label":"Wet (your choice)"},
 "at":"2026-09-25T22:30:00-04:00"},"error":null,"model_version":"pp-20260926-1902-f49c0d2"}
```

Errors: 404 `OUTSIDE_CITY`; 422 `BAD_TIME`, `BAD_REQUEST`; 503 `CITY_PULSE_UNAVAILABLE`.

---

## Community street reports (MongoDB Atlas)

Reports are context only: they never change a score, a route choice, or explanation evidence.

### `POST /reports`

Body (extra fields forbidden): `{seg_id: int ≥ 0, category}` where `category` ∈ `sidewalk_blocked`, `signal_out`, `construction`, `poor_lighting`, `flooding`, `fast_traffic`. There is no free-text field and no client location: the street name and point come from the bundle's walk graph (midpoint of the segment's first walk edge). One atomic upsert on the unique `(seg_id, category)` index: a repeat report increments `confirmations` and extends expiry to 14 days from now.

Response `ReportOut`: `seg_id`, `category`, `label`, `street`, `lon`, `lat`, `confirmations`, `updated_at`, `expires_at`. Errors: 404 `NOT_FOUND`; 422 `BAD_REQUEST`; 503 `REPORTS_UNAVAILABLE`; 429.

### `GET /reports`

`bbox` query: `minLon,minLat,maxLon,maxLat`, ≤ 120 chars, finite, ordered, each span ≤ 0.3°. Wider or malformed boxes are refused with 422 `BAD_BBOX` (not truncated). Returns up to 300 active reports (`$geoWithin` on the 2dsphere index), most-confirmed first.

### `GET /reports/summary`

Aggregation per category over active reports: `{category, label, reports, confirmations}[]`, sorted by confirmations. Live sample: `{"success":true,"data":[],"error":null,...}`.

---

## Share my walk (MongoDB Atlas)

### `POST /walks` → 201

Body (extra fields forbidden):

| Field | Type | Limits |
| --- | --- | --- |
| `destination` | `{label, lat, lon}` | label 1–120 chars (trimmed); coordinates finite |
| `eta_s` | int | 0–43,200 |
| `route` | `[lon, lat][]` \| null | ≤ 2,000 points |

Destination and every route point must fall in a metro-Atlanta box (−84.85..−83.95, 33.35..34.25) or 422 `OUTSIDE_AREA`.

Response `CreatedWalkOut`: `walk_id` (128 random bits, URL-friendly base64), `owner_token` (256 random bits; **returned only here**; the server stores its SHA-256), `follow_path` (`/follow/{walk_id}`), `expires_at` (now + 6 h).

### `PUT /walks/{walk_id}/position`

`walk_id` ≤ 128 chars and must match `[A-Za-z0-9_-]{16,64}` (else 404). Body (extra fields forbidden): `owner_token` (16–128 chars), `lat`, `lon` (finite, metro box), `accuracy_m` (0–10,000, optional), `eta_s` (0–43,200, optional), `status` (`walking`\|`arrived`\|`ended`, optional).

Rules: gate check (one accepted update per 3 s per walk, status changes exempt) → load → constant-time token-hash comparison → ended walks stay ended (summary returned unchanged) → area check → optimistic-concurrency write conditioned on the previous `updated_at` → `expires_at` moves to now + 6 h.

Response `WalkSummaryOut`: `walk_id`, `status`, `destination`, `eta_s` (seconds left; 0 unless walking), `eta_at`, `position` (`lat, lon, accuracy_m, at`) or null, `updated_at`, `expires_at`. Never includes the token or its hash.

Errors: 403 `WALK_FORBIDDEN`; 404 `WALK_NOT_FOUND`; 422 `OUTSIDE_AREA`, `BAD_REQUEST`; 429 `WALK_THROTTLED` (gate, per-walk interval, or a concurrent write); 503 `WALKS_UNAVAILABLE`.

### `GET /walks/{walk_id}`

What a follower sees: `WalkSummaryOut` plus `route`. Expired walks read as 404 even before the TTL monitor deletes them.

```json
{"success":false,"data":null,"error":{"code":"WALK_NOT_FOUND","message":"This shared walk has ended or the link has expired."},"model_version":"pp-20260926-1902-f49c0d2"}
```

---

## Personal-safety layer

All three return 503 `SAFETY_UNAVAILABLE` when the bundle has no safety files. Crime data here is informational; it is never an input to routing or the traffic model.

### `GET /safety/meta`

`{data_through, sources: {name, url, license}[], crime_categories: string[], day_parts: {key, label, hours}[]}`.

### `GET /safety/hexes`

| Parameter | Type | Limits |
| --- | --- | --- |
| `bbox` | string | as `/reports` (≤ 0.3° span) |
| `hour` | int | 0–23, optional (default: current Atlanta hour); selects the day part |

Response `SafetyHexOut[]` (hexes whose centers are within the box padded by 0.003°, max 4,000): `h3`, `lat`, `lon`, `crimes_persons_12mo`, `crime_band` (`lower`/`typical`/`higher`), `lit_share` (null when under half of walkable length is known), `activity_band` (`quiet`/`moderate`/`busy`/null), `help_points`.

```json
{"success":true,"data":[{"h3":"8944c1a8123ffff","lat":33.756347,"lon":-84.392019,"crimes_persons_12mo":11,"crime_band":"higher",
 "lit_share":1.0,"activity_band":"busy","help_points":0}, "..."],"error":null,"model_version":"..."}
```

### `GET /safety/help-points`

`bbox` as above. Response `{kind: "blue_light"|"police"|"fire"|"hospital"|"marta", name, lat, lon}[]` (max 1,000).

---

## Transit

### `GET /transit/stations`

MARTA heavy-rail stations inside the coverage bounding box (28 of the 38 in `backend/app/domain/marta_stations.json`): `{name, lat, lon, lines}[]`. Used for the MARTA hand-off card on walks longer than 25 minutes.

---

## Static bundle files

`GET /static/{model_version}/{file}`. In production Caddy serves `/srv/pathpulse/artifacts/{version}/{file}` directly with `Cache-Control: public, max-age=31536000, immutable`; the API also mounts the same directory. Any version still on disk is reachable, which is why version-pinned caching can use an immutable header. File formats are listed in [data_and_models.md §11](data_and_models.md#11-bundle-layout).

## Error code index

| Code | HTTP | Raised by |
| --- | --- | --- |
| `BAD_REQUEST` | 422 | Request validation; `/explain` without `seg_id` |
| `BAD_TIME` / `BAD_DEPARTURE` | 422 | Unparseable or out-of-range time |
| `BAD_BBOX` | 422 | `/reports`, `/safety/hexes`, `/safety/help-points` |
| `OUT_OF_COVERAGE` | 422 | `/routes` |
| `SNAP_TOO_FAR` | 422 | `/routes` (> 150 m from the graph) |
| `TOO_CLOSE` | 422 | `/routes` (< 60 m) |
| `NO_CONNECTION` | 422 | `/routes` |
| `OUTSIDE_AREA` | 422 | `/walks*` |
| `WALK_FORBIDDEN` | 403 | Wrong owner token |
| `NOT_FOUND` | 404 | Unknown segment |
| `OUTSIDE_CITY` | 404 | `/areas*` |
| `ROUTE_EXPIRED` | 404 | `/explain`, `/tts` for a route not in cache |
| `WALK_NOT_FOUND` | 404 | Unknown or expired walk |
| `RATE_LIMITED` | 429 | Middleware |
| `WALK_THROTTLED` | 429 | Share-my-walk update gate or race |
| `INTERNAL` | 500 | Unhandled exception |
| `MODE_UNAVAILABLE` | 503 | Ride mode without a ride model |
| `HISTORY_UNAVAILABLE` | 503 | Tiger Data |
| `REPORTS_UNAVAILABLE` | 503 | MongoDB Atlas (reports) |
| `WALKS_UNAVAILABLE` | 503 | MongoDB Atlas (walks) |
| `SAFETY_UNAVAILABLE` | 503 | No safety layer |
| `CITY_PULSE_UNAVAILABLE` | 503 | No City Pulse files |
| `TTS_UNAVAILABLE` | 503 | ElevenLabs |

Demo-only codes returned by the browser's offline transport (never by the server): `DEMO_ONLY`, and the 503-style codes above for features the demo hides.
