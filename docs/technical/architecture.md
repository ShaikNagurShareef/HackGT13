# PathPro system architecture

PathPro forecasts where and when people on foot (and on bikes and scooters) are exposed to traffic crashes in Atlanta. It shows that forecast as an hourly map (Risk Tides), uses it to plan lower-risk routes, explains scores in plain language (text and voice), illustrates evidence-based street fixes, and answers questions about itself (Ask PathPro). This document describes how the running system is put together. It is written from the code in `backend/app`, `frontend/src`, `data/src/pathpulse_data`, and `deploy/`, as of bundle `pp-20260926-1902-f49c0d2`.

| Fact | Value | Where it comes from |
| --- | --- | --- |
| Live site | https://pathpro.tech (also `www.pathpro.tech` and `155-138-233-35.sslip.io`) | `deploy/go.sh`, `deploy/Caddyfile` |
| Host | One Vultr VM in Atlanta (`atl`, `vc2-1c-2gb`, Ubuntu 24.04), IP 155.138.233.35 | `deploy/provision_vultr.sh` |
| Model bundle served | `pp-20260926-1902-f49c0d2` | `artifacts/current` symlink, `/meta` |
| Street segments (risk units) | 49,915 road segments across the City of Atlanta | `manifest.json` → `n_segments` |
| Walk routing graph | 84,758 nodes, 120,763 edges (99,119 inherit a road segment) | `manifest.json` → `walk_graph` |
| Ride routing graph | 49,824 nodes, 65,997 edges (53,158 inherit a road segment) | `manifest.json` → `ride_graph` |
| City Pulse grid | 3,537 H3 resolution-9 hexes | `manifest.json` → `n_hexes` |
| API process | FastAPI under uvicorn, one worker, bound to 127.0.0.1:8000 | `deploy/pathpulse.service` |

What the system produces (captured with Playwright from the offline demo, except City Pulse, which comes from the live site; see `docs/images/gallery/README.md`):

| Phone and personal-safety views | Desktop and City Pulse views |
| --- | --- |
| **Fastest vs PathPro route (phone)**<br>![Phone route comparison: +4 min for 54% less traffic-risk exposure](../images/gallery/02-phone-route-comparison.png) | **Risk Tides on desktop**<br>![Desktop sidebar with Risk Tides re-coloring street segments by hour](../images/gallery/04-desktop-risk-tides-home.png) |
| **Personal-safety mode with fairness note and help points**<br>![Personal-safety mode](../images/gallery/06-personal-safety-fairness-help-points.png) | **City Pulse area score with its factors**<br>![City Pulse area card](../images/gallery/07-city-pulse-area-score-live.png) |

Related documents: [data and models](data_and_models.md), [API reference](api_reference.md), [deployment and operations](deployment_operations.md), [security and privacy](security_privacy.md), [testing and quality](testing_quality.md).

---

## 1. Design principles that shape the architecture

1. **The model bundle is the hot path.** Every score, route, and explanation is computed from files loaded into memory at startup (`repositories/artifacts.py`). No database sits on the request path for routing or scoring (PRD NFR-04).
2. **Every external dependency is optional.** LLMs (xAI Grok, Groq, Gemini), voice (Grok Voice, ElevenLabs), Grok Imagine, Backboard, geocoding, weather, Tiger Data, and MongoDB Atlas each have a fallback. Missing keys turn a feature off; they never stop the app (section 9).
3. **No model-generated number reaches the user.** Scores and factor points come from the traffic model. Explanation LLMs only rewrite server-built evidence, Ask PathPro answers may quote only numbers found in the docs, the on-screen context, or the question, and validators withhold anything else (sections 6.2 and 6.6). Clients send ids, never prompt text.
4. **Crime never reaches routing or the traffic model.** The personal-safety layer passes only lighting and foot-traffic codes to the router (section 8).
5. **Generated media is labeled and checked.** Grok Imagine pictures are drawn from a server-written prompt, reviewed by Gemini before they are cached, and always shown as an AI illustration, never as a photo or a risk claim (section 6.5).
6. **Versioned, immutable artifacts.** A bundle directory is named by model version, every file is hashed in `manifest.json`, and the browser fetches model files from `/static/<model_version>/` with a one-year immutable cache header.

---

## 2. Context (C4 level 1)

```mermaid
flowchart TB
  walker(["Walker or rider<br/>(phone or desktop browser)"])
  friend(["Friend following<br/>a shared walk"])
  dev(["Developer laptop<br/>(data pipeline, deploy and setup scripts)"])
  pp["PathPro at pathpro.tech<br/>traffic-risk map, lower-risk router,<br/>explanations, voice, street redesign illustrations,<br/>Ask PathPro, share-my-walk"]
  subgraph ext["External services (each optional)"]
    xai["xAI<br/>Grok chat, Grok Voice, Grok Imagine"]
    groq["Groq API<br/>gpt-oss-120b / gpt-oss-20b"]
    gemini["Gemini API<br/>explanations, image check"]
    eleven["ElevenLabs TTS"]
    backboard["Backboard<br/>Ask PathPro: docs RAG,<br/>opt-in memory clones"]
    geoapify["Geoapify autocomplete"]
    meteo["Open-Meteo forecast"]
    tiger[("Tiger Data<br/>TimescaleDB + PostGIS")]
    mongo[("MongoDB Atlas<br/>street reports, shared walks")]
  end
  tiles["OpenFreeMap vector tiles"]
  open["Public open data<br/>ARC, City of Atlanta, CAP, Georgia Tech,<br/>APD, StreetLight, OSM, Open-Meteo archive"]
  walker -->|HTTPS| pp
  friend -->|"HTTPS /follow/{walk_id}"| pp
  walker -->|basemap tiles| tiles
  pp --> xai
  pp --> groq
  pp --> gemini
  pp --> eleven
  pp --> backboard
  pp --> geoapify
  pp --> meteo
  pp --> tiger
  pp --> mongo
  open -->|ArcGIS REST, Overpass| dev
  dev -->|"versioned bundle (rsync over SSH)"| pp
  dev -->|"load_tiger (COPY)"| tiger
  dev -->|"setup_backboard: docs corpus,<br/>prune_backboard: stale clones"| backboard
```

*Figure A1. System context.* PNG: [img/a1_context.png](img/a1_context.png)

- **Users** reach one origin. The browser also loads basemap tiles directly from OpenFreeMap (allowed by the CSP `img-src`/`connect-src`). Every AI provider is called by the server; no key or provider URL reaches the browser.
- **The model is built offline.** The `data/` pipeline runs on a developer machine, pulls public layers with no accounts, and ships a bundle directory to the VM. The server never trains or fetches training data.
- **Tiger Data** is the system of record for crashes and the versioned score grid. The API reads it for exactly one feature: the "when crashes happened here" hourly chart.
- **MongoDB Atlas** stores user-generated state: community street reports and Share-my-walk sessions. Neither feeds the model.
- **xAI** serves three features: Grok writes explanations (first in the chain), Grok Voice reads them aloud (first voice), and Grok Imagine draws street redesign illustrations. **Gemini** is both an explanation fallback and the reviewer of every Grok Imagine picture (a separate model setting). **Backboard** hosts the Ask PathPro assistant: retrieval over six project documents, plus opt-in private memory clones. The laptop tools `setup_backboard` and `prune_backboard` create the assistant and clean up old clones.

---

## 3. Containers (C4 level 2)

```mermaid
flowchart LR
  subgraph browser["Browser"]
    spa["React 19 SPA (Vite)<br/>MapLibre GL + deck.gl<br/>zod-validated API client"]
    local[("localStorage<br/>learned routines,<br/>Ask memory token")]
    session[("sessionStorage<br/>share-walk owner token,<br/>Ask thread token")]
  end
  subgraph vm["Vultr VM (Ubuntu 24.04, 1 vCPU, 2 GB)"]
    caddy["Caddy 2<br/>auto-HTTPS, security headers,<br/>zstd/gzip, filtered JSON access log"]
    web["/srv/pathpulse/web<br/>SPA build + demo fixtures"]
    art["/srv/pathpulse/artifacts/{version}<br/>model bundle files"]
    api["uvicorn + FastAPI 'PathPro API'<br/>1 worker on 127.0.0.1:8000<br/>systemd unit pathpulse.service"]
    mem[("In-process state<br/>walk + ride bundles, routers,<br/>LRU caches, rate limiter, daily budgets,<br/>per-client caps, walk gate")]
    imgcache[("/var/cache/pathpulse-imagine<br/>Grok Imagine images + check sidecars<br/>(systemd CacheDirectory)")]
    docs["/srv/pathpulse/app/docs<br/>Ask corpus: allowed numbers"]
  end
  subgraph saas["Managed services"]
    tiger[("Tiger Data")]
    mongo[("MongoDB Atlas")]
    xai["xAI: Grok chat,<br/>Grok Voice, Grok Imagine"]
    llm["Groq, Gemini"]
    tts["ElevenLabs"]
    bb["Backboard"]
    geo["Geoapify"]
    wx["Open-Meteo"]
  end
  spa -->|"GET / and /demo/*"| caddy
  spa -->|"GET /static/{version}/*"| caddy
  spa -->|"/api/* JSON, MP3, images"| caddy
  caddy --> web
  caddy --> art
  caddy -->|"reverse_proxy, /api stripped"| api
  api --- mem
  api -->|reads bundle at startup| art
  api -->|"reads corpus at startup"| docs
  api -->|"read / atomic write"| imgcache
  api -->|"psycopg, 800 ms statement timeout"| tiger
  api -->|"pymongo async, 1.5 s op timeout"| mongo
  api -->|httpx| xai
  api -->|httpx| llm
  api -->|httpx| tts
  api -->|"httpx, 12 s"| bb
  api -->|httpx| geo
  api -->|httpx| wx
  spa --- local
  spa --- session
```

*Figure A2. Containers.* PNG: [img/a2_containers.png](img/a2_containers.png)

| Container | Technology | Responsibility | State |
| --- | --- | --- | --- |
| SPA | React 19, Vite 8, TypeScript 6, MapLibre GL 5, deck.gl 9, zod 4 | Map, Risk Tides playback, search, route sheets, navigation, share, safety layers, street redesign illustrations, Ask PathPro panel | URL query (view state), localStorage (routines, Ask memory token), sessionStorage (share session, Ask thread token) |
| Caddy | Caddy 2 (apt), config `deploy/Caddyfile` | TLS for three hostnames, security headers, static files, `/api/*` proxy | Certificates, JSON access log `/var/log/caddy/pathpulse.log` |
| API | FastAPI, uvicorn `--workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1` | Routing, scoring, attribution, explanations, voice, Grok Imagine and its Gemini check, Ask PathPro, geocoding proxy, reports, shared walks, safety queries | In memory (section 4.3), plus the image cache below |
| Image cache | Directory `IMAGINE_CACHE_DIR`: `/var/cache/pathpulse-imagine` in production (systemd `CacheDirectory`), `backend/cache/imagine/` locally (gitignored) | One checked Grok Imagine picture per street segment and image model, with a JSON check sidecar | Survives restarts; the API's only writable path in production |
| Bundle | Files under `/srv/pathpulse/artifacts/<version>/`, `current` symlink | Model outputs: factors, frames, graphs, geometry, metrics | Immutable per version; old versions kept |
| Tiger Data | TimescaleDB + PostGIS (managed) | `crashes` hypertable, `crashes_hourly` continuous aggregate, `segments`, `risk_grid` | System of record |
| MongoDB Atlas | M0 cluster, collections `street_reports`, `shared_walks` | User-generated context and live sharing | TTL-expiring documents |
| Backboard | Hosted assistant API (`app.backboard.io/api`) | Ask PathPro: retrieval over six uploaded docs, conversation threads, opt-in visitor memory clones | Assistant, documents, threads, and clones live in the Backboard account |

---

## 4. Backend internals

### 4.1 Layers

| Package | Role | Examples |
| --- | --- | --- |
| `app/api/` | FastAPI routers, request/response schemas, the response envelope, dependencies | `core.py` (`/healthz`, `/meta`, `/routes`, `/segments/{id}`), `extras.py` (`/explain`, `/tts`, `/geocode`, `/conditions/live`, hourly history), `areas.py`, `reports.py`, `walks.py`, `safety.py`, `transit.py`, `imagine.py`, `ask.py`, `ask_context.py` (what an Ask question is about), `envelope.py` |
| `app/services/` | Use cases that combine domain logic with I/O | `routing.py` (coverage, snapping, copy), `segments.py`, `areas.py`, `explain/` (`evidence.py`, `resolve.py`, `providers.py`, `validator.py`, `template.py`, `service.py`), `tts.py` (voice chain), `imagine.py`, `imagine_check.py`, `ask.py`, `ask_corpus.py`, `ask_memory.py`, `ask_threads.py`, `backboard.py` (REST client), `limits.py` (per-client daily caps), `weather.py`, `geocode.py`, `reports.py`, `walks.py`, `safety.py` |
| `app/domain/` | Pure logic, no I/O | `router.py` (Dijkstra ladder), `route_metrics.py`, `scoring.py` (percentile scale, attribution), `alerts.py`, `timeutil.py`, `modes.py`, `safety.py`, `walks.py`, `reports.py`, `transit.py` |
| `app/repositories/` | Data access with tight timeouts | `artifacts.py` (bundle loader), `hexes.py`, `safety.py`, `history.py` (Tiger), `reports.py` and `walks.py` (Atlas) |
| `app/tools/` | Operator CLIs, not served | `check_keys.py` (verifies each sponsor key without printing it), `record_demo.py` (records the offline demo), `setup_backboard.py` (creates the Ask PathPro assistant and uploads its docs), `prune_backboard.py` (deletes stale memory clones) |

### 4.2 Startup (`create_app` in `app/main.py`)

1. `load_bundle(ARTIFACTS_DIR)` loads the walk model and **fails fast**: a missing file or a SHA-256 mismatch against `manifest.json` raises `BundleError`, and the process does not start.
2. `load_safety(...)` loads the personal-safety layer if all five safety files exist and their shapes match the walk graph; otherwise `None`.
3. `Router(bundle, safety.edges)` builds the walk router (directed edge arrays, a k-d tree for snapping, parallel-edge index).
4. `load_ride_bundle(root)` loads the `ride_`-prefixed model if `ride_graph.npz` exists; any error disables ride modes and logs a warning. A second `Router` is built for it.
5. `load_hexes(root)` loads City Pulse if `hex_meta.json` exists.
6. In-memory objects: a 512-entry LRU of recent `RoutesData` (evidence for `/explain`), the rate limiter, and the Share-my-walk update gate.
7. Repositories for Tiger Data and Atlas are constructed **without I/O**. The lifespan hook creates one shared `httpx.AsyncClient` and, from it, every provider-facing service: the explanation chain (`build_providers`: Grok, Groq 120b, Gemini, Groq 20b, each only when its key is set), geocoding, the voice chain (`build_voices`: Grok Voice, then ElevenLabs), Ask PathPro and its memory (`build_ask`: reads the allowed-number corpus from `docs/`, and derives thread and memory token signers from `ASK_THREAD_SECRET` or a random per-process secret), and Grok Imagine with its Gemini checker. It then asks Atlas to ensure indexes (failure only logs a warning).
8. Middleware: `CORSMiddleware` (added last, so outermost) wraps `RateLimitMiddleware`. Exception handlers render every error as the standard envelope.
9. The bundle directory is also mounted at `/static/<model_version>` by FastAPI (Caddy serves the same path from disk in production).

### 4.3 In-process state and the single worker

Several features rely on memory that is local to one process:

| State | Where | Consequence |
| --- | --- | --- |
| `routes_cache` (LRU 512) | `app.state.routes_cache` | `POST /explain {kind: "route"}` finds the route by `route_key`. A different process, or a restart, returns `ROUTE_EXPIRED` (404) and the client re-requests the route. |
| Explanation cache (LRU 4,096) and single-flight locks | `ExplainService` | One LLM call per unique evidence key, per process. |
| Rate-limit windows (TTL cache, 50,000 clients) | `RateLimitMiddleware` | Limits are per process. |
| Share-my-walk update gate (TTL cache, 10,000 walks) | `RecentUpdates` | Floods are rejected before any Atlas read. |
| Daily budgets for LLM, geocoding, each voice, Grok Imagine, Ask, and memory clones | `DailyBudget` | Counters reset at local midnight and on restart. |
| Per-client daily caps (Grok Imagine 10, Ask 20, memory clones 3) | `ClientDailyLimit` (TTL cache, 50,000 clients) | Keyed like the rate limiter; reset on restart. |
| TTS audio caches (LRU 256 per voice) and alert clips (LRU 512) | `GrokTtsService`, `TtsService`, `AlertAudio` | Repeat Listen taps and repeated navigation starts reuse audio. |
| Grok Imagine single-flight locks | `ImagineService` | Repeated taps on one street make one paid call. |
| Ask token secret (when `ASK_THREAD_SECRET` is unset) | `build_ask` | Thread and memory tokens stop verifying after a restart; the asker starts a new thread and memory reads as off. |

The Grok Imagine images themselves are on disk, so they survive restarts. The systemd unit runs `--workers 1` so the in-memory state behaves as designed. At about 120 ms of CPU per route (the router runs in `asyncio.to_thread` to keep the event loop free), one worker fits a hackathon load on a 1-vCPU VM. Scaling out would need a shared store for the route cache and limiter.

### 4.4 Frontend structure

| Area | Files | Notes |
| --- | --- | --- |
| Shell | `main.tsx`, `App.tsx`, `app/PathPro.tsx` | `initRuntime()` resolves the API origin before first render (same-origin on the VM). `PathPro` owns view state and wires the data hooks. |
| API client | `api/client.ts`, `api/schemas.ts`, `api/safetySchemas.ts`, `api/walks.ts`, `api/safety.ts` | Every response is parsed with a zod schema wrapped in the envelope schema; an 8 s abort timeout; non-JSON bodies become a friendly `SERVER` error. |
| Demo transport | `api/demo.ts` | With `?demo=1`, `request()` answers from `/demo/fixtures.json` instead of the network (section 6.4). |
| Bundle loading | `hooks/useBundle.ts`, `hooks/bundleFiles.ts`, `hooks/useRideNetwork.ts` | Loads `/meta`, then `segments.geojson`, `hotspot_nodes.json`, `hex_cells.json` from `meta.static_base`. The ride geometry and frames load only when a ride mode is first chosen. |
| Risk Tides frames | `frames/frameStore.ts`, `hooks/useRiskFrames.ts` | One `Uint8Array` per (day group, condition); `hour(h)` is a zero-copy `subarray`, so scrubbing never touches the network after the first fetch (PRD NFR-02). |
| Map | `map/MapView.tsx`, `map/layers.ts`, `map/hexLayer.ts`, `map/safetyLayers.ts`, `map/FollowMap.tsx` | MapLibre basemap with deck.gl `PathLayer`, `ScatterplotLayer`, `SolidPolygonLayer`, and H3 hex layers. |
| On-device features | `lib/routines.ts`, `lib/shareSession.ts`, `hooks/useNavigation.ts`, `hooks/useGeolocation.ts`, `lib/alertClips.ts`, `hooks/useAlertClips.ts` | Routines are learned in localStorage only; navigation follows the GPS watch and speaks alerts (server-voice clips prefetched from `/tts/alert`, else the device voice); nothing about walk history is sent to the server. |
| View state | `state/urlState.ts` | Origin, destination, departure, condition, hour, day, segment, preference, and mode live in the URL so a view survives refresh. |
| Street redesign | `components/ImagineStreet.tsx` | "Imagine this street redesigned" in the street sheet: sends only the segment id (75 s client timeout), shows the picture with its AI-illustration label, the fix list, and "Checked by Gemini: shows N of M planned fixes". Hidden in `?demo=1`. |
| Ask PathPro | `components/ask/AskPanel.tsx`, `components/ask/AskMemoryControls.tsx`, `lib/askContext.ts`, `lib/askMemory.ts` | A dialog with suggested questions and "Ask about this street / route / area" entry points. The context names only ids, times, and conditions (never GPS, places, or routines). Thread token in sessionStorage, opt-in memory token in localStorage (`pathpro:ask-memory:v1`), 15 s client timeout. Hidden in `?demo=1`. |

---

## 5. How a score is computed at request time

Every score in the product comes from one identity that the pipeline enforces (checked to within 1e-6 at export):

```
log density(segment, cell) = base + Σ spatial factor(segment) + Σ temporal factor(cell)
score = percentile of that log density on the bundle's 1,001-point citywide quantile table (0–100)
cell  = (day group, hour, light, wet)   # Atlanta local time; light from solar elevation
```

- `Bundle.log_density()` is one vector addition, so the router can score all 240k directed edges for a departure in a single NumPy pass.
- `domain/scoring.attribute()` splits a displayed score into a baseline, the top five factors, and a remainder, by adding factors from largest to smallest effect and assigning each the score change it causes. The integers always sum to the score (property-tested on 200 random cases in `backend/tests/test_scoring.py`).
- Bands: Lower 0–24, Moderate 25–49, Elevated 50–74, High 75–100.

Details of how the factors are fitted are in [data_and_models.md](data_and_models.md).

---

## 6. Request flows

### 6.1 Plan a route

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (SPA)
  participant C as Caddy
  participant A as FastAPI
  participant W as WeatherService
  participant R as Router (worker thread)
  participant M as MongoDB Atlas
  participant L as LLM chain<br/>(Grok, Groq, Gemini)
  participant E as Voice<br/>(Grok Voice, ElevenLabs)
  participant T as Tiger Data
  B->>C: POST /api/routes {origin, destination, depart_at, cond, prefer?, mode?}
  C->>A: POST /routes (prefix stripped, X-Forwarded-For set)
  A->>A: rate limit (general bucket) and pydantic validation
  A->>A: mode_context: walk bundle, or ride_ bundle (503 MODE_UNAVAILABLE)
  A->>A: parse departure, city-hex coverage check, snap both ends within 150 m
  A->>W: resolve(cond, departure)
  W-->>A: dry or wet, source live / override / assumed
  A->>R: asyncio.to_thread(router.plan)
  Note over R: fastest path, then 7 cost-ladder candidates,<br/>each re-scored at its traversal times,<br/>best one inside the detour budget
  R-->>A: RoutePlan (fastest, pathpro or none, message code)
  A->>A: alerts, safety summary (walk only), route_key = sha256(...)[:16]
  opt walk mode and Atlas configured
    A->>M: active reports on the recommended route (0.5 s budget)
    M-->>A: reports, or [] on any failure
  end
  A->>A: routes_cache[route_key] = RoutesData
  A-->>B: {success, data: RoutesData, model_version}
  rect rgb(238, 243, 250)
    Note over B,T: Follow-up calls the route sheet makes
    B->>A: POST /api/explain {kind: route, route_key}
    A->>L: evidence JSON (see 6.2)
    L-->>A: 1 to 3 sentences, validated
    A-->>B: {text, source}
    B->>A: POST /api/tts (same body, only on Listen)
    A->>E: server-written text
    E-->>A: MP3 from the first voice that answers<br/>(or 503, then device voice)
    B->>A: POST /api/tts/alert {route_key, index, kind} (navigation start, up to 12 clips, 2 at a time)
    A->>E: server-written alert line from the cached route
    E-->>A: MP3 (cached per route, kind, index, voice) or 503, then device voice
    B->>A: GET /api/segments/{id}/hourly (street sheet)
    A->>T: SELECT from crashes_hourly (800 ms timeout)
    T-->>A: 24 hourly sums (or 503, chart hidden)
  end
```

*Figure A3. Plan-a-route sequence.* PNG: [img/a3_route_sequence.png](img/a3_route_sequence.png)

What the router does (`domain/router.py`, `domain/route_metrics.py`):

| Step | Rule |
| --- | --- |
| Too close | Origin and destination on the same node or under 60 m apart → `TOO_CLOSE` |
| Search area | Directed edges inside a box around the trip padded by max(1,200 m, 0.6 × trip distance); if the box cuts the only connection, the whole graph is searched |
| Fastest path | Dijkstra (SciPy `csgraph`) on travel time at the mode's speed (walk 1.3 m/s; bike 15, e-bike 22, scooter 18 km/h) |
| Candidates | Dijkstra with cost = time × (1 + λ × density / density at score 75) for λ ∈ {0.05, 0.1, 0.25, 0.5, 1, 2, 4} |
| Re-scoring | Each candidate is re-scored edge by edge at the minute the walker would reach that edge (light and hour can change mid-trip) |
| Detour budget | min(1.25 × fastest duration, fastest + 6 min) |
| Pick | Lowest expected-crash exposure inside the budget; shown only if it is ≥10 score points lower or has ≥15% less exposure, else "The fastest route is already the lower-risk option." |
| Trade-off note | If a candidate outside the budget cuts exposure a further ≥15%, the message says how many minutes it would add |
| Long trips | Walk: > 5 km or > 1 h; ride: > 15 km or > 1 h → `long_trip` message suggesting MARTA |
| Lit and busy | Walk only, after dark only, opt-in: see section 8 |

### 6.2 "Why?" explanations

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser
  participant A as FastAPI /explain
  participant R as explain/resolve.py
  participant X as ExplainService
  participant GK as Grok (xAI)
  participant G1 as Groq gpt-oss-120b
  participant GM as Gemini
  participant G2 as Groq gpt-oss-20b
  participant V as Validator
  participant TP as Template
  B->>A: {kind: segment, seg_id, t, cond, mode} or {kind: route, route_key}
  A->>A: paid rate-limit bucket
  A->>R: resolve evidence (ids only from the client)
  alt kind = route
    R->>R: routes_cache lookup (404 ROUTE_EXPIRED if missing), route_evidence()
  else kind = segment
    R->>R: segment_detail() then segment_evidence()
  end
  R-->>A: cache key + Evidence (strings cleaned: no control chars, max 80 chars)
  A->>X: explain(cache key, Evidence)
  alt cache hit
    X-->>A: text, source "cache"
  else miss (single-flight lock per key)
    X->>X: daily budget check (default 3,000 generations/day)
    X->>GK: system prompt + evidence JSON (first provider, max 1.6 s)
    GK-->>X: text
    X->>V: numbers, clock times, banned words, max 3 sentences, max 420 chars
    alt valid
      X-->>A: text, source "grok"
    else rejected, timeout, or error
      Note over X,G2: each next provider gets the remaining time of a 4 s total
      X->>G1: same evidence
      G1-->>X: text, then validate
      X->>GM: same evidence (if still rejected)
      GM-->>X: text, then validate
      X->>G2: same evidence (if still rejected)
      G2-->>X: text, then validate
      alt every provider rejected or failed
        X->>TP: render(evidence)
        TP-->>X: deterministic text, source "template" (not cached)
      end
    end
  end
  A-->>B: {text, source}
```

*Figure A4. Explanation chain.* PNG: [img/a4_explain_sequence.png](img/a4_explain_sequence.png)

- **Evidence is the only LLM input.** `services/explain/resolve.py` rebuilds the evidence from ids (a segment id, a cached route key, or, for Ask PathPro, an H3 cell), and `services/explain/evidence.py` turns it into a JSON payload (street name, score, band, time label, conditions, confidence, up to three factors that raise risk and one that lowers it, crash history; or, for routes, minutes, scores, extra minutes, exposure reduction, and avoided streets). No user text is included. Street names come from OpenStreetMap, which anyone can edit, so every evidence string is flattened before any LLM sees it: control characters and newlines become spaces and each string is cut to 80 characters.
- **Cache keys** include the model version: `seg:{id}:{day|hour|light|wet}:{version}[:{mode}]` and `route:{route_key}:{version}`.
- **Validator** (`services/explain/validator.py`) rejects text that is empty, longer than 420 characters, longer than three sentences, contains a banned framing, contains a clock time other than the evidence time, or contains any number not present in the evidence (numbers inside evidence strings such as street names or "2020-2024" count as grounded).
- **Provider order** is built in `main.build_providers`: xAI Grok (`XAI_MODEL`, default `grok-4.20-0309-non-reasoning`), Groq (`GROQ_MODEL`, default `openai/gpt-oss-120b`), Gemini (`GEMINI_MODEL`, default `gemini-3.8-flash`), then Groq (`GROQ_FALLBACK_MODEL`, default `openai/gpt-oss-20b`). The response `source` is `grok`, `groq`, `gemini`, `groq-20b`, `template`, or `cache`. A missing key drops that provider; with no keys, every answer is the template. The first provider gets at most 1.6 s (`GROQ_BUDGET_S`) and the chain 4 s in total (`EXPLAIN_BUDGET_S`).
- **Truncation is a failure.** Grok and Groq answers (both OpenAI-compatible) must finish with `finish_reason == "stop"` and Gemini with `finishReason == "STOP"`; otherwise the next provider is tried. All providers share one system prompt and the same validator.
- **Voice.** `POST /tts` takes the same request body, regenerates (usually from cache) the server's own explanation, and sends that text to the voice chain (`services/tts.py`): Grok Voice (`https://api.x.ai/v1/tts`, voice `XAI_TTS_VOICE`, default `eve`, MP3), then ElevenLabs (`eleven_flash_v2_5`). Each voice has a 6 s timeout, a 420-character cap, an LRU audio cache, and its own daily budget (`TTS_DAILY_BUDGET`). If neither answers, the endpoint returns 503 and the browser speaks with its device voice. Clients cannot supply text to speak.
- **Navigation alerts.** `POST /tts/alert {route_key, index, kind}` speaks one alert stretch of a cached route through the same voice chain (`services/alert_voice.py`). The server writes the line, "High traffic risk ahead." plus up to three cleaned street names, with no distance; the body forbids extra fields, so no client text can be spoken. Clips are cached in memory (LRU 512, per route, kind, index, and voice). At navigation start the SPA prefetches up to 12 clips, 2 at a time, stopping at the first failure; any alert without a clip, and every alert in `?demo=1`, is spoken by the device voice with its distance.

### 6.3 Share my walk

```mermaid
sequenceDiagram
  autonumber
  participant W as Walker's browser
  participant A as FastAPI /walks
  participant G as In-memory update gate
  participant M as MongoDB Atlas (shared_walks)
  participant F as Friend's browser
  W->>A: POST /walks {destination, eta_s, route?}
  A->>A: paid bucket, metro-Atlanta box check
  A->>A: walk_id = 128 random bits, owner_token = 256 random bits
  A->>M: insert {walk_id, sha256(token), status walking, expires_at = now + 6 h}
  A-->>W: 201 {walk_id, owner_token (returned once), follow_path, expires_at}
  W->>W: keep session in sessionStorage (this tab only)
  W-->>F: share /follow/{walk_id} (Web Share or copy)
  loop every 5 s while walking
    W->>A: PUT /walks/{id}/position {owner_token, lat, lon, accuracy_m, eta_s, status}
    A->>G: accepted in the last 3 s? (status changes skip this)
    G-->>A: throttle (429 WALK_THROTTLED) or continue
    A->>M: find walk (expires_at > now)
    A->>A: compare_digest(sha256(token), stored hash) else 403
    A->>M: find_one_and_update where updated_at = previous, set position, expires_at = now + 6 h
    M-->>A: updated walk (or none on a race: 429)
    A->>G: mark accepted
    A-->>W: WalkSummary (no token, no hash)
  end
  F->>A: GET /walks/{id}
  A->>M: find walk (expires_at > now)
  A-->>F: position, destination, ETA, status, route (no token, no hash)
  Note over M: TTL index on expires_at deletes the document<br/>6 h after the last accepted update
```

*Figure A5. Share-my-walk sequence.* PNG: [img/a5_share_sequence.png](img/a5_share_sequence.png)

- `PUT /walks/{id}/position` stays on the **general** rate limit on purpose (many walkers share one venue NAT address); the in-memory gate absorbs floods before Atlas is touched. Only authenticated, saved updates mark the gate, so a stranger holding the follow link cannot throttle the walker.
- A walk with status `ended` stays ended; later updates return the summary unchanged.
- In `?demo=1`, sharing is simulated on the device and nothing is sent.

### 6.4 Offline demo (`?demo=1`)

```mermaid
flowchart TB
  rec["backend/app/tools/record_demo.py<br/>runs create_app in a TestClient"] -->|"234 recorded responses"| fx["frontend/public/demo/fixtures.json<br/>(committed)"]
  rec -->|"copies geometry and frames"| st["frontend/public/demo/static/{version}/<br/>(gitignored, built into the SPA)"]
  url["Browser opens /?demo=1"] --> isdemo{"isDemoMode()"}
  isdemo -->|yes| load["loadFixtures(): fetch fixtures.json once, up front"]
  load --> req["api/client.request()"]
  req --> key["fixtureKey(method, path, body)<br/>e.g. 'POST /routes 33.7771,-84.3962>33.7810,-84.3863|wet'"]
  key -->|recorded| ans["recorded envelope"]
  key -->|not recorded| off["DEMO_ONLY / MODE_UNAVAILABLE error envelope"]
  req -->|"/geocode"| empty["[] (curated places still work)"]
  req -->|"/reports*"| hide["REPORTS_UNAVAILABLE (feature hidden)"]
  req -->|"/safety/*"| saf["recorded safety fixtures or SAFETY_UNAVAILABLE"]
  load --> meta["GET /meta fixture: static_base = /demo/static/{version}"]
  meta --> st
```

*Figure A6. Offline demo transport.* PNG: [img/a6_demo_flow.png](img/a6_demo_flow.png)

- The scripted scenario is Klaus Building → Midtown MARTA and Tech Square → North Ave MARTA, Friday 22:30, with wet, dry, and live conditions, for walk, bike, e-bike, and scooter.
- Recorded: `/meta`, `/conditions/live`, 24 route responses, 52 explanations, segment details for every top segment, three City Pulse lookups, safety meta, help points, 24 hourly safety hex sets, and MARTA stations (234 keys).
- `frontend/e2e/demo.spec.ts` loads the page, then calls `context.setOffline(true)` and runs the full route, preview-walk, and copy checks with the network off.
- Features that need a live provider are hidden in the demo instead of being recorded: the "Imagine this street redesigned" button (`ImagineStreet` returns nothing when `isDemoMode()`), and every Ask PathPro entry point (`askAvailable={!demo}`).

### 6.5 "Imagine this street redesigned" (Grok draws, Gemini checks)

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (street sheet)
  participant A as FastAPI /imagine
  participant S as ImagineService
  participant D as Disk cache<br/>/var/cache/pathpulse-imagine
  participant X as xAI Grok Imagine
  participant G as Gemini check<br/>(gemini-3.1-flash-lite)
  B->>A: POST /imagine/segment {seg_id} (only an id)
  A->>A: paid rate-limit bucket, extra fields forbidden
  A->>S: plan_for_segment(seg_id) at a fixed weekday 9 PM, dry
  Note over S: prompt from the street's risk factors and road class,<br/>never street names or user text
  S->>D: seg-{id}-{model}.img exists?
  alt cached
    D-->>S: image + check sidecar
    S-->>A: cached = true (no xAI call, no budget used)
  else not cached
    S->>S: no xAI key: 503 IMAGINE_UNAVAILABLE
    S->>S: single-flight lock per segment
    S->>S: per-client cap (10/day, 429 IMAGINE_CLIENT_LIMIT),<br/>then daily budget (40/day, 429 IMAGINE_BUDGET)
    S->>X: prompt, 16:9, 1k, b64_json (60 s)
    X-->>S: PNG or JPEG (signature checked, max 8 MB) or 502 IMAGINE_FAILED
    S->>G: image + planned fixes, JSON schema, temperature 0 (25 s)
    alt passes (no readable text or logos, no identifiable faces)
      G-->>S: fixes_shown (exact planned phrases only)
      S->>D: sidecar, then image (atomic writes)
    else flagged
      G-->>S: has_text_or_logos or has_identifiable_faces
      S->>X: one retry (takes another budget unit)
      Note over S: flagged twice, or no budget: 502 IMAGINE_REJECTED, nothing cached
    else Gemini unreachable, no key, or malformed answer
      G-->>S: unchecked
      S->>D: image + sidecar {"by": null}
    end
    S-->>A: cached = false
  end
  A-->>B: {image_url, prompt_summary, fixes, label, cached, check}
  B->>A: GET /imagine/segment/{id}.png
  A->>D: read (never calls xAI)
  A-->>B: image, Cache-Control max-age=86400, nosniff
  Note over B: shown with "AI illustration of evidence-based street fixes<br/>by Grok Imagine — not a real photo" and<br/>"Checked by Gemini: shows N of M planned fixes"
```

*Figure A9. Street redesign illustration.* PNG: [img/a9_imagine_sequence.png](img/a9_imagine_sequence.png)

The street sheet offers an AI illustration of the street with evidence-based design fixes (`services/imagine.py`, `api/imagine.py`). It is a picture for planners and curious walkers; it never changes a score.

- **The prompt is written by the server.** `POST /imagine/segment` accepts only `{seg_id}` (extra fields forbidden). `plan_for_segment` reads the segment's detail at a fixed reference hour (a weekday at 9 PM, dry) so a street always gets the same plan, maps each factor that raises its traffic risk to a street-design fix (for example speed → narrower lanes and raised crosswalks; intersection or crash history → high-visibility crosswalks with curb extensions; mostly after-dark crash history → pedestrian-scale lighting), keeps up to four fixes, and describes the scene by road class. The prompt never contains a street name or user text, and asks for no text, logos, or lettered signs.
- **Grok draws.** One call to `https://api.x.ai/v1/images/generations` (`XAI_IMAGE_MODEL`, default `grok-imagine-image-2.0`; 16:9, 1k, base64; 60 s). The bytes must start with a PNG or JPEG signature and be at most 8 MB.
- **Gemini checks.** `services/imagine_check.py` sends the image and the planned fix list to Gemini (`GEMINI_CHECK_MODEL`, default `gemini-3.1-flash-lite`, separate from the explanation model so free-tier quotas do not collide) with a JSON response schema at temperature 0 and a 25 s timeout (a vision review of a 1k image regularly took more than 8 s live). The answer is parsed strictly: only fix phrases that exactly match the planned list survive, and the two flags must be booleans. An image with readable text or logos, or an identifiable face, is rejected and redrawn once (taking another budget unit); a second rejection returns 502 `IMAGINE_REJECTED` and nothing is cached. If Gemini is unreachable, unconfigured, or answers malformed JSON, the image is kept as **unchecked** (`check: null`) rather than blocked.
- **Cache and limits.** Checked images are written atomically to `IMAGINE_CACHE_DIR` as `seg-{id}-{model}.img`, with a `.check.json` sidecar written first. A cached street costs nothing and uses no limit. New generations are single-flight per segment and capped per client address (`IMAGINE_PER_CLIENT_DAILY`, 10) and in total (`IMAGINE_DAILY_BUDGET`, 40) per day. `GET /imagine/segment/{id}.png` only ever reads the cache.
- **Labeling.** The API returns and the UI shows the label "AI illustration of evidence-based street fixes by Grok Imagine — not a real photo", the plan summary, and "Checked by Gemini: shows N of M planned fixes" when the check ran.

### 6.6 Ask PathPro (Backboard)

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (Ask panel)
  participant A as FastAPI POST /ask
  participant C as ask_context + explain/resolve
  participant S as AskService
  participant T as ThreadTokens (HMAC)
  participant BB as Backboard assistant<br/>(RAG over 6 docs)
  participant V as Ask validator
  B->>A: {question, thread_id?, memory_token?, context?: segment | route | area ids}
  A->>A: paid rate-limit bucket, question 3 to 300 chars,<br/>one line (else 422 BAD_QUESTION)
  A->>A: no Backboard key or assistant id: 503 ASK_UNAVAILABLE
  A->>C: resolve context on the server
  alt street, route, or area resolves
    C-->>A: Evidence from the model (no coordinates, no cell id)
  else no context, or it cannot be resolved
    C-->>A: live-conditions Evidence (day, hour, light, dry/wet),<br/>context_dropped = true when a named context failed
  end
  A->>S: ask(question, thread token, client, evidence, memory token)
  S->>S: per-client cap 20/day (429 ASK_CLIENT_LIMIT)
  S->>T: verify thread token bound to this assistant
  T-->>S: thread UUID, or none (a new thread)
  S->>S: shared daily budget 300/day (spent: fallback answer)
  S->>BB: context block + question, memory "Readonly"<br/>(or the visitor's clone, see Figure A11), 12 s
  BB-->>S: answer with retrieval citations
  S->>S: strip citation and bold markers
  S->>V: links, on-topic, length, banned words,<br/>crime framing, every number sourced
  alt passes
    V-->>S: ok
    S->>T: sign the thread UUID for this assistant
    S-->>A: answer, source "backboard", sources (allow-listed docs)
  else rejected, timeout, upstream error, or budget spent
    S-->>A: fixed fallback that points to the model card, source "fallback"
  end
  A-->>B: {answer, thread_id (signed), source, note, sources, memory, context_used, context_dropped}
  Note over B: thread token kept in this tab's sessionStorage only
```

*Figure A10. Ask PathPro question flow.* PNG: [img/a10_ask_sequence.png](img/a10_ask_sequence.png)

Ask PathPro answers questions about how PathPro works and about the street, route, or City Pulse area on screen (`services/ask.py`, `api/ask.py`, `api/ask_context.py`).

- **Retrieval corpus.** `app.tools.setup_backboard` creates one Backboard assistant with a strict system prompt and uploads six documents (`services/ask_corpus.py`): `docs/model_card.md`, `docs/metrics.json`, `docs/safety_sources.md`, `docs/decisions.md`, `docs/technical/data_and_models.md`, and `docs/judge_qa.md`, plus five read-only facts in its memory. At startup the API reads the same files from disk to build the set of numbers an answer may quote. A missing file contributes nothing, so with no corpus every number is rejected (fail closed).
- **Context built on the server.** The request names what is on screen by id only (`{kind: segment, seg_id, t, cond, mode}`, `{kind: route, route_key}`, or `{kind: area, cell, t, cond}`). `ask_context.py` rebuilds the evidence with the same resolvers as `/explain` (`explain/resolve.py`); area evidence carries neither the cell id nor coordinates. Without context, or when it cannot be resolved (an expired route, an unknown street), the question gets live-conditions evidence only (day, hour, light, dry or wet) and the response says `context_dropped: true`; it is never an error. The evidence rides above the question as a JSON block the assistant is told to treat as data for this question only.
- **Validation.** The raw answer has citation and bold markers stripped, then must pass `ask_validation_errors`: no links, domains, or email addresses except `pathpro.tech` and the six corpus file names; on topic (at least one PathPro term); at most 140 words and 1,000 characters; none of the explanation validator's banned words, except that the words for the personal-safety layer and crime data may appear, plus a few extra place framings (income and demographics may be named only in a sentence saying they are not used); no crime framing of places, and crime named next to routing, scores, or the model only with a negation; and every number found in the corpus, the context evidence, or the question itself. Anything else, and any upstream error, the 12 s timeout, or a spent daily budget, returns a fixed fallback that points to the model card (`source: "fallback"`). Raw LLM text is never shown or logged.
- **Sources.** Retrieval citations that name an allow-listed corpus file become `sources` links to that file on GitHub; the model can never choose a URL.
- **Threads.** The browser never holds a bare Backboard id. Thread ids are returned as HMAC-signed tokens bound to the assistant they belong to (`services/ask_threads.py`); a forged, stale, or mismatched token is never forwarded and simply starts a new thread.
- **Limits.** Paid rate-limit class, 20 questions per client address per day (`ASK_PER_CLIENT_DAILY`, checked first), and 300 per day in total (`ASK_DAILY_BUDGET`).

### 6.7 Ask PathPro opt-in memory

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser
  participant A as FastAPI /ask*
  participant M as AskMemory
  participant K as MemoryTokens (HMAC)
  participant BB as Backboard
  Note over B: memory is off by default
  B->>A: POST /ask/memory {} ("Remember my preferences")
  A->>M: enable(client)
  M->>M: per-client 3 clones/day, global 100/day<br/>(429 ASK_MEMORY_LIMIT)
  M->>BB: clone the shared docs assistant<br/>(documents + read-only facts, name pathpro-visitor-{12 hex})
  BB-->>M: clone assistant id (must be a UUID, never the base id)
  M->>K: sign clone id (purpose ask-memory)
  A-->>B: {memory_token}
  Note over B: token kept in localStorage (this browser),<br/>any change starts a new thread
  B->>A: POST /ask {question, memory_token, context?}
  A->>K: verify memory token
  alt valid token, plain question (no street, route, or area context)
    A->>BB: clone assistant, memory "Auto" + memory note
    Note over BB: fact extraction prompt keeps only stated travel<br/>preferences: times, mode, well-lit or busier streets,<br/>accessibility. Never places, streets, routes, or context.
  else valid token, question about a street, route, or area
    A->>BB: clone assistant, memory "Readonly" (reads, never writes)
  else missing or invalid token
    A->>BB: shared assistant, memory "Readonly" (memory: off)
  end
  BB-->>A: answer (validated as in Figure A10)
  A-->>B: answer, memory "on" or "off"
  B->>A: POST /ask/memory/forget {memory_token} ("Forget me")
  A->>M: forget(token)
  alt token verifies
    M->>BB: DELETE /assistants/{clone} (404 counts as done)
  else token does not verify
    M->>M: silent no-op (never reveals validity)
  end
  A-->>B: {forgotten: true} (502 ASK_MEMORY_FORGET_FAILED on upstream error)
  Note over BB: prune_backboard deletes pathpro-visitor-* clones<br/>older than 30 days (the shared assistant is never touched)
```

*Figure A11. Opt-in private memory.* PNG: [img/a11_ask_memory.png](img/a11_ask_memory.png)

- **Off by default.** Without a memory token every question goes to the shared assistant with Backboard memory `Readonly`, so no visitor can write the shared memory.
- **Turning it on** (`POST /ask/memory`) clones the shared assistant (documents and read-only facts included) into a private assistant named `pathpro-visitor-<12 hex>`, and returns an HMAC-signed memory token (a separate token purpose from threads). The browser keeps it in localStorage; pausing memory keeps the token, and any change starts a new thread because a thread belongs to one assistant. Each client address may create three clones a day, under a global cap of 100 (`ASK_MEMORY_DAILY`).
- **What is written.** Memory mode is `Auto` only for plain questions (no street, route, or area context), which is where people state preferences; a question carrying on-screen context uses the clone with `Readonly`. The clone inherits a structured fact-extraction prompt (set by `setup_backboard`, verified live) that keeps only travel preferences a person states about themselves: usual times, travel mode, a preference for well-lit or busier streets, and accessibility needs. It never keeps places, addresses, streets, routes, names, or anything inside the context block.
- **Forget me** (`POST /ask/memory/forget`) deletes the clone and everything it remembered. It is idempotent (an upstream 404 counts as done) and never reveals whether a token was valid: an unverifiable token is a silent no-op.
- **Housekeeping.** `app.tools.prune_backboard --older-than 30d [--dry-run]` deletes `pathpro-visitor-*` clones older than the given age, never touches the shared assistant, keeps clones without a readable creation time, and prints counts only.

---

## 7. Multi-mode design (walk vs ride)

```mermaid
flowchart LR
  subgraph dir["artifacts/{version}/ (one directory, one manifest)"]
    wfiles["Walk model (bare names)<br/>seg_meta.json, factors.json,<br/>spatial_factors.npy, walk_graph.npz,<br/>segments.geojson, frames_*.bin,<br/>hotspot_nodes.json, metrics.json"]
    rfiles["Ride model (ride_ prefix)<br/>ride_seg_meta.json, ride_factors.json,<br/>ride_spatial_factors.npy, ride_graph.npz,<br/>ride_segments.geojson, ride_frames_*.bin,<br/>ride_hotspot_nodes.json, ride_metrics.json"]
    shared["Shared layers<br/>hex_* (City Pulse), safety_*, help_points.json,<br/>segment_safety.npy, edge_safety.npy, coverage.geojson"]
    man["manifest.json<br/>sha256 of every file, modes.walk, modes.ride"]
  end
  wfiles -->|"load_bundle(prefix='') required, fail fast"| wb["walk Bundle + Router<br/>(with EdgeSignals)"]
  rfiles -->|"load_ride_bundle() optional"| rb["ride Bundle + Router"]
  man --> wb
  man --> rb
  req["request mode = walk | bike | ebike | scooter"] --> ctx{"mode_context()"}
  ctx -->|walk| wb
  ctx -->|"bike / ebike / scooter"| rb
  ctx -->|"ride bundle missing"| e503["503 MODE_UNAVAILABLE"]
  meta["/meta modes[].static_prefix"] --> spa["SPA loads {prefix}segments.geojson<br/>and {prefix}frames_* on first use"]
```

*Figure A7. One bundle, two travel networks.* PNG: [img/a7_multimode.png](img/a7_multimode.png)

- **Same code path, different prefix.** `load_bundle(root, prefix)` reads `{prefix}seg_meta.json`, `{prefix}factors.json`, `{prefix}spatial_factors.npy`, and `walk_graph.npz` or `ride_graph.npz`. The walk loader verifies every non-`ride_` file; the ride loader verifies only `ride_` files, so a broken ride file can never block walking.
- **Same risk units.** Both models score the same 49,915 road segments and share segment ids. Only the routing graph (OSMnx `walk` vs `bike` network), the training label, the ride-only features, and the frames differ.
- **Mode-specific behaviour.** Ride modes plan at the mode's speed, use the ride long-trip threshold (15 km), skip community reports and the personal-safety summary, ignore the `lit_and_busy` preference, and report `bike_crashes` in segment history. Route cache keys and explanation cache keys add `|mode=...` only for ride modes, so walk keys are unchanged.
- **Frontend.** `/meta` lists four modes with `available`, `speed_kmh`, `network`, and `static_prefix`. `useRideNetwork` downloads `ride_segments.geojson` and `ride_frames_*` only the first time a ride tab is chosen, so walkers never download them.

---

## 8. Personal-safety layer

```mermaid
flowchart LR
  apd["APD crimes against persons<br/>(4 offenses, public places only)"] --> hexc["per H3 res-9 hex x day part<br/>12-month counts + EB posterior band"]
  osm["OSM lit tags, street lamps,<br/>City downtown lights"] --> lit["per walk edge: lit / unlit / unknown"]
  sl["StreetLight pedestrian activity (2021)"] --> act["per edge and hex: quiet / moderate / busy<br/>by day part"]
  help["GT call boxes, police, fire,<br/>hospitals, MARTA"] --> hp["help points + per-hex counts"]
  hexc --> hexfile["safety_hexes.json"]
  lit --> edgefile["edge_safety.npy<br/>(lit + 4 activity codes, no crime)"]
  act --> edgefile
  act --> hexfile
  hp --> hpfile["help_points.json"]
  edgefile --> sig["EdgeSignals"]
  sig --> router["Router: lit_and_busy penalty<br/>(after dark, opt-in)"]
  hexfile --> disp["GET /safety/hexes (map layer)"]
  hexfile --> summ["RouteOut.safety.crimes_persons_nearby<br/>(display only)"]
  hpfile --> disp2["GET /safety/help-points,<br/>help points within 100 m"]
  hexfile -. "no path" .-x router
```

*Figure A8. Personal-safety data flow: crime is display-only.* PNG: [img/a8_safety_flow.png](img/a8_safety_flow.png)

- **What reaches the router.** `EdgeSignals` holds only a lighting code per walk edge and an activity band per day part (`repositories/safety.py`). There is no crime field in it, and a test (`test_crime_counts_never_change_the_route`) builds bundles with crime counts scaled by 0, 1, and 1,000 and asserts that every plan is identical for both preferences.
- **The `lit_and_busy` preference** (walk only, after dark by the same solar-elevation rule as the model): each edge's cost is multiplied by 1 + 1.0 × [known unlit] + 0.5 × [known quiet in the departure's day part]. Unknown values are neutral. The ladder is re-run with λ = 0 plus the usual seven values; candidates must fit the detour budget and add at most 10% traffic exposure over the fastest route; the winner must cut penalty-weighted unlit-or-quiet length by at least 15% against the route the default plan would show, otherwise the default plan is returned unchanged.
- **Route summary.** For walks, `RouteOut.safety` reports `lit_share` and `busy_share` (by length, `null` when under half the route is known), help points within 100 m (polyline densified every 20 m), and `crimes_persons_nearby` (12-month count for the day part over the hexes crossed). The summary is informational.
- **Copy.** Every crime surface carries the fairness note: "Reported incidents, grouped by area and time of day. Reports reflect where police record incidents, not how people should feel about a neighborhood. PathPro never routes around neighborhoods based on crime."

---

## 9. Graceful degradation

| Dependency | How it fails | What the user sees | Code |
| --- | --- | --- | --- |
| Walk model bundle | Missing file or SHA-256 mismatch | API does not start (fail fast); systemd restarts it every 2 s; Caddy returns 502 for `/api` while the SPA still loads | `repositories/artifacts.py`, `deploy/pathpulse.service` |
| Ride model files | Absent or unreadable | Bike, E-bike, and Scooter tabs show as unavailable; `/routes` with a ride mode returns 503 `MODE_UNAVAILABLE`; walking unaffected | `load_ride_bundle`, `api/deps.mode_context` |
| City Pulse files | Absent | `/areas*` return 503 `CITY_PULSE_UNAVAILABLE`; coverage checks fall back to the bounding box | `repositories/hexes.py`, `services/routing.in_coverage` |
| Safety files | Absent or shape mismatch | `/safety/*` return 503 `SAFETY_UNAVAILABLE`; routes have `safety: null`; `lit_and_busy` behaves like the default | `repositories/safety.load_safety` |
| xAI Grok (explanations) | No key, timeout, HTTP error, truncated or ungrounded text | Next provider (Groq); the user still gets a sentence | `services/explain/service.py` |
| Groq | Same | Next provider; the user still gets a sentence | same |
| Gemini | Same | Next provider, then the template | same |
| All LLMs / daily budget spent | No providers or budget exhausted | Deterministic template text (`source: "template"`), never cached | `template.py`, `DailyBudget` |
| Grok Voice | No xAI key, over 420 chars, budget spent, HTTP error or timeout (6 s) | ElevenLabs is tried next (explanations and navigation alerts) | `services/tts.py`, `services/alert_voice.py` |
| ElevenLabs | No key or voice, over 420 chars, budget spent, HTTP error | `/tts` returns 503 `TTS_UNAVAILABLE`; the browser speaks with its own voice | `services/tts.py` |
| Grok Imagine | No xAI key; upstream error or timeout (60 s); per-client or daily cap reached | Already-cached streets still show their picture; new ones get 503 `IMAGINE_UNAVAILABLE`, 502 `IMAGINE_FAILED`, or 429 `IMAGINE_CLIENT_LIMIT` / `IMAGINE_BUDGET` with a friendly message | `services/imagine.py` |
| Gemini image check | No key, timeout (25 s), error, malformed answer | The picture is kept and shown as unchecked (`check: null`); a picture Gemini flags twice is never shown (502 `IMAGINE_REJECTED`) | `services/imagine_check.py` |
| Backboard | No key or assistant id | `/ask*` return 503 `ASK_UNAVAILABLE`; the panel says Ask PathPro can't answer right now and points to the model card in About PathPro | `services/ask.py`, `services/ask_memory.py` |
| Backboard | Timeout (12 s), HTTP error, unexpected response, answer withheld by the validator, daily budget spent | A fixed fallback answer that points to the model card (`source: "fallback"`); memory on/off and forget return 502 codes and Ask keeps working without memory | same |
| Geoapify | No key, fewer than 3 characters, budget spent, timeout (2.5 s) | `/geocode` returns `[]`; the curated place list (`lib/places.ts`) still works | `services/geocode.py` |
| Open-Meteo | Timeout (4 s) or error | Cached forecast used for up to 1 h; after that "Live weather unavailable — using dry conditions." (`source: "assumed"`) | `services/weather.py` |
| Tiger Data | Unset, unreachable (3 s connect), slow (800 ms statement) | Hourly chart hidden (503 `HISTORY_UNAVAILABLE`); `/healthz` reports `database` and `status: degraded` | `repositories/history.py` |
| MongoDB Atlas (reports) | Unset | Report UI hidden; `/reports*` 503 `REPORTS_UNAVAILABLE`; routes carry `reports: []` | `repositories/reports.py` |
| MongoDB Atlas (reports) | Unreachable or slow | Same, plus a 30 s cooldown after any failure; routes wait at most 0.5 s | same |
| MongoDB Atlas (walks) | Unset, unreachable, cooling down | 503 `WALKS_UNAVAILABLE` "Live sharing is unavailable right now. Navigation still works." | `repositories/walks.py`, `services/walks.py` |
| Network (client) | Offline or timeout (8 s) | "You're offline. Map still works; routing needs a connection." Frames already fetched keep playing | `api/client.ts`, `frames/frameStore.ts` |
| Browser storage | Blocked or corrupt | Routines and share resume silently disabled; zod-validated reads drop bad data | `lib/routines.ts`, `lib/shareSession.ts` |

---

## 10. Performance

| Measure | Value | Source |
| --- | --- | --- |
| `POST /routes`, walk, in-process on a developer Mac (40 trips 0.8–3 km, Friday 22:30, dry, real bundle, no external calls) | See [testing_quality.md §6](testing_quality.md#6-latency-sample) | Measured for this document |
| Route planning p95 before and after the citywide router refactor | 1.95 s → 0.26 s | Commit `c8d5e8f` message |
| Default and lit-and-busy plans computed together, 40 random night trips 0.8–2.5 km | p50 154 ms, p95 283 ms | `docs/safety_sources.md` |
| Risk Tides frame | 24 × 49,915 bytes = 1,197,960 bytes per (day group, condition); City Pulse 24 × 3,537 = 84,888 bytes | Bundle files |
| Frame swap after first fetch | No network: `subarray` view per hour | `frames/frameStore.ts` |

PRD targets for reference: `POST /routes` p95 < 1.5 s (NFR-03); frame swap < 100 ms (NFR-02).
