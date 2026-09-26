# Security, privacy, and responsible AI

What PathPro protects, how, and where the controls live in code. Everything below was checked against the code and the live headers of https://pathpro.tech on 2026-09-26.

## 1. Threat model summary

PathPro has no user accounts, no payments, and no personal profiles. The assets worth protecting are small but real:

| Asset | Threat | Main controls |
| --- | --- | --- |
| Sponsor API keys (LLM, voice, geocoding, databases, Vultr) | Leak through the browser, git, logs, or terminal output | Keys only in `backend/.env`; server-side proxying; `SecretStr`; type-only error logging; gitleaks pre-commit hook; masked key helpers (section 8) |
| Paid quotas | Cost abuse by scripted clients | Paid rate-limit class, daily budgets, caching, single-flight LLM calls (section 5) |
| A walker's live location (Share my walk) | Hijacking or reading someone else's walk | 128-bit unguessable walk ids, 256-bit owner tokens stored only as SHA-256, constant-time comparison, 6 h TTL, metro-area bounds (section 3) |
| Users' trust in the numbers | Hallucinated or alarming explanations | Evidence-only LLM input, validator, template fallback, banned framings (section 7) |
| Neighbourhoods and the people in them | Stigmatizing areas, demographic proxies, crime-driven routing | No demographic, income, or crime features in any model; crime is display-only with a fairness note; tested (section 9) |
| Service availability | Floods, slow dependencies | Rate limits, timeouts on every call, cooldowns, graceful degradation, a fully offline demo |
| Server | Remote code execution, lateral movement | Loopback-only API behind Caddy, hardened systemd unit, ufw, no shell-outs or dynamic SQL on the request path (section 6) |

Out of scope for a hackathon deployment: DDoS protection beyond the per-client limits, WAF, and multi-region failover.

## 2. Data minimization

| Data | What is kept | What is never kept |
| --- | --- | --- |
| Crash records (pipeline) | Location, timestamp, year, pedestrian/cyclist flags, severity letter, reported light and surface, road names | Names, ages, narratives, map URLs (`PII_COLUMNS` in `ingest/clean.py` are dropped or never selected) |
| Reported crimes (safety layer) | Per H3 res-9 hex × day part counts and bands only | Addresses, report numbers, victim fields, points. The fetch requests only `OccurredFromDate, NIBRS_Offense, LocationType` and geometry; residences, apartments, jails, and shelters are excluded; sex offenses are not included |
| Routing requests | Nothing persisted. The last 512 route results sit in process memory for `/explain` | Origin and destination are not written to any database |
| Learned routines | Browser `localStorage` only (`pathpro:routines:v1`, max 200 trips), zod-validated, one tap clears | Nothing is sent to the server |
| Share-my-walk session in the browser | `sessionStorage` only (this tab), never `localStorage` or the URL | |
| Shared walks (Atlas) | Destination label and point, ETA, latest position and accuracy, optional route, status, timestamps, SHA-256 of the owner token | The token itself; any user identity. The TTL index deletes the document 6 h after the last update |
| Community reports (Atlas) | Segment id, one of six fixed categories, street name and point **from the bundle**, confirmation count, timestamps | Free text, reporter identity, the reporter's location. TTL removes a report 14 days after its last confirmation |
| Analytics | None: no analytics or tracking scripts in the SPA, no cookies set by PathPro | |

Known gap: Caddy's JSON access log (`/var/log/caddy/pathpulse.log`) records client IP, user agent, and full request URIs, including query strings such as `/api/areas/lookup?lat=…&lon=…`, `/api/geocode?q=…`, and map viewport boxes. Request bodies (route origins and destinations, walk positions) are not logged. The PRD's NFR-09 asked for coordinates in logs to be rounded to about 100 m; that rounding is not implemented. The log lives only on the VM.

## 3. Input validation

Every request body and parameter is a pydantic model or a typed FastAPI parameter; failures become 422 `BAD_REQUEST` without echoing validator details.

| Surface | Validation |
| --- | --- |
| Coordinates | `lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`; Share-my-walk also rejects NaN/Infinity and anything outside a metro-Atlanta box |
| Times | `t`/`depart_at` ≤ 40 chars; `now`, `+Nm`, `+Nh` (≤ 3 digits) or ISO-8601 within 400 days |
| Enums | `cond`, `mode`, `prefer`, `kind`, report `category`, walk `status` are `Literal` types |
| Ids and keys | `seg_id ≥ 0` and range-checked against the bundle; `route_key` `^[0-9a-f]{16}$`; H3 `cell` `^[0-9a-f]{15}$`; `walk_id` ≤ 128 chars and `[A-Za-z0-9_-]{16,64}` before any lookup; owner token 16–128 chars |
| Viewports | `bbox` ≤ 120 chars, four finite ordered numbers, each span ≤ 0.3°; wider boxes are refused rather than truncated |
| Strings | Geocode `q` 1–80 chars; walk destination label 1–120 chars (trimmed); route ≤ 2,000 points; ETA ≤ 12 h |
| Unknown fields | `extra="forbid"` on report and walk request models |
| Server-derived data | Report location and street name come from the bundle, never the client; `/tts` speaks only server-generated text |
| Untrusted upstream data | Atlas documents are re-validated on read (`parse_report`, `parse_walk`) and malformed ones skipped; the SPA zod-validates every API response and every browser-storage read |
| Output shape | Separate response models, so tokens and hashes cannot leak into walk responses |

Database access uses parameterized queries (`psycopg` `%s` placeholders in `repositories/history.py`) and structured Mongo filters; no query is built by string concatenation from user input.

## 4. Authentication and authorization

There are no accounts. The only authorization decision is "may this client update this shared walk?":

- `walk_id` = `secrets.token_urlsafe(16)` (128 bits). Anyone with the follow link can **read** the walk; ids are not enumerable.
- `owner_token` = `secrets.token_urlsafe(32)` (256 bits), returned once at creation; the database stores `sha256(token)`; comparison uses `hmac.compare_digest`.
- Updates are conditional on the previous `updated_at` (optimistic concurrency), so racing writes cannot overwrite each other.
- The in-memory update gate records only authenticated, saved updates, so a follower who knows the walk id cannot throttle the walker.

## 5. Rate limiting and cost control

| Control | Setting | Code |
| --- | --- | --- |
| General limit | 300 requests / min / client (`RATE_LIMIT_PER_MINUTE`) | `middleware.py` |
| Paid/write limit | 30 / min / client on `/explain`, `/geocode`, `/tts`, `POST /reports`, `POST /walks` (`PAID_RATE_LIMIT_PER_MINUTE`) | same |
| Client identity | `request.client.host` set by uvicorn from `X-Forwarded-For` only for the trusted local proxy (`--forwarded-allow-ips 127.0.0.1`); raw headers from the internet cannot spoof it. IPv6 grouped by /64 | same, `pathpulse.service` |
| Memory bound | Rate-limit state in a TTL cache capped at 50,000 clients | same |
| Daily budgets | LLM 3,000, Geoapify 2,500, ElevenLabs 500 calls per day | `DailyBudget` |
| Caching | Explanations (LRU 4,096, keyed by evidence and model version), TTS audio (LRU 256), geocode results (1 h) | services |
| Single flight | Concurrent requests for one explanation share one LLM call | `ExplainService.explain` |

Why `PUT /walks/{id}/position` stays on the general limit: at the expo every visitor shares the venue's NAT address, and each walker posts about 12 updates a minute. Counting those against the 30/min paid bucket would let three walkers lock out the whole hall. The protection moves to the resource instead: `RecentUpdates` rejects a second update for the same walk within 3 s (status changes excepted) before any Atlas read, and `POST /walks` (which creates documents) stays on the paid limit.

## 6. Transport and browser hardening

Headers set by Caddy on every response (verified live):

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(self)
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src https://fonts.gstatic.com; img-src 'self' data: blob: https://tiles.openfreemap.org;
  connect-src 'self' https://tiles.openfreemap.org; worker-src 'self' blob:; child-src blob:; media-src 'self' blob:;
  frame-ancestors 'none'; base-uri 'self'; object-src 'none'
(Server header removed)
```

- `script-src 'self'`: no inline or third-party scripts. `'unsafe-inline'` is allowed for styles only (MapLibre and component styles).
- `worker-src blob:` and `child-src blob:` are needed by MapLibre's web workers; `media-src blob:` plays TTS audio.
- CORS: explicit origin list, methods `GET, POST, PUT`, header `Content-Type`, no credentials.
- The API binds to 127.0.0.1; ufw exposes only 22, 80, 443. The systemd unit runs as an unprivileged user with `ProtectSystem=strict`, `ProtectHome=true`, `ReadOnlyPaths=/srv/pathpulse`, `NoNewPrivileges`, `PrivateTmp`, an empty capability set, `LockPersonality`, and `RestrictSUIDSGID`.
- Errors never include stack traces (`unexpected_error_handler`).

## 7. LLM guardrails

The explanation chain is Groq → Gemini → Groq (smaller model) → deterministic template (`services/explain/`).

| Guardrail | Implementation |
| --- | --- |
| No user text reaches the prompt | The user message is `Evidence (<kind>):\n<JSON>`, built entirely from server data (`evidence.py`) |
| The LLM never produces a score | Scores, bands, and factor points come from the model; the prompt says "Every number you write must appear in it" |
| Grounding check | `validator.py` extracts every number (after removing evidence strings such as street names and "2020-2024") and every clock time; any number not in the evidence, or a time other than the evidence time label, rejects the text |
| Length and truncation | ≤ 3 sentences, ≤ 420 characters; completions that did not finish normally are rejected |
| Banned framing | Case-insensitive word-boundary match on: safe, safest, safer, safety, guarantee, guaranteed, crime, criminal, dangerous area, dangerous neighborhood, bad neighborhood, bad area, sketchy, unsafe, violent, shooting, robbery, income, race, demographic |
| Prompt rules | Say "traffic risk", "lower-risk", "historical crashes"; never mention people, neighborhoods, or demographics; at most three factors and one action; ride modes say "riding" |
| Fallback | Any failure, timeout, or rejection moves to the next provider; the template is always valid and is not cached (so a transient outage does not stick) |
| Voice | `/tts` speaks only text the server produced for the same request |
| Community reports | Never included in evidence |

UI copy is held to the same rules by tests: `frontend/src/components/safety/copy.test.tsx` renders every personal-safety surface and asserts none contains safe, safest, unsafe, dangerous, bad area, sketchy, or guaranteed; `frontend/e2e/demo.spec.ts` checks the rendered demo page ("copy never promises safety").

## 8. Secret handling and the key-masking incident

- **Where secrets live.** `backend/.env` only (gitignored; `.env.example` lists names). On the VM the file is streamed with `umask 077` and set to mode 0600.
- **Never in the browser.** Geoapify, ElevenLabs, and LLM calls are proxied by the API.
- **Never in logs.** Settings use `SecretStr`; failures log `type(exc).__name__` only (exception text from database drivers can echo a connection string); `httpx` logging is raised to WARNING because Geoapify takes its key as a query parameter.
- **Operator tools.** `app.tools.check_keys` verifies each key with one live call and prints only OK/MISSING/FAIL. The key-capture helpers write matching strings straight to `backend/.env`.

**Incident (commit `41dd776`, Sat 2026-09-26 11:02 ET).** The browser helper that saved newly created sponsor keys into `backend/.env` masked key-like strings in its own terminal output with a word-boundary regular expression. When the output was JSON, an escaped newline (`\n`) sat directly against a key, the word boundary did not match, and one key was printed unmasked in a local terminal session. It was never committed or deployed. Fix: JSON output is now decoded and each string value is masked individually, and non-JSON output has escaped newlines expanded before masking. The exposed key was flagged for revocation in `docs/sponsor_checklist.md` (the deploy uses a separate, newly created key). Lesson recorded: mask decoded values, not serialized text.

**Scanning.**

- `.pre-commit-config.yaml` runs **gitleaks** (v8.21.2) on every commit, plus ruff, ruff-format, `check-added-large-files` (5 MB), `check-merge-conflict`, and `end-of-file-fixer`. The hook is installed in this clone (`.git/hooks/pre-commit`).
- `gitleaks detect` over the full history (131 commits at the time of writing, run with gitleaks 8.30.1): **no leaks found**.
- `gitleaks dir .` over the working tree flags only `backend/.env`, the intended, gitignored secrets file.
- Dependency pinning: `uv.lock` (Python, installed with `--frozen` on the VM) and `package-lock.json` (installed with `npm ci`). No automated vulnerability scanner (for example `pip-audit` or `npm audit` in CI) is configured.

## 9. Fairness safeguards

| Safeguard | Evidence |
| --- | --- |
| No demographic, income, race, or crime features in the traffic models | Feature list in `model/dataset.py`; ARC income, race, and environmental-justice flags are never read (`network/features.ARC_STRUCTURAL`); the ARC baseline is labelled "demographic flags removed" |
| Crime never enters routing | `EdgeSignals` (the only safety input to the router) holds lighting and activity codes, no crime; `backend/tests/test_safety_router.py::test_crime_counts_never_change_the_route` builds bundles with crime counts × 0, × 1, × 1,000 and asserts identical plans for both route preferences |
| Crime never enters explanations | Evidence builders read only traffic-model output; the validator also rejects crime vocabulary |
| No stigma from empty data | Crime bands use an exposure-normalized Empirical-Bayes posterior; a hex with zero reports can never be "higher" (`safety/banding.py`, tested in `data/tests/test_safety_crime.py`) |
| Unknown is not bad | Unknown lighting is never treated as unlit; unknown activity is neutral in routing |
| Always-on context | The fairness note appears wherever crime counts do |
| Narrow crime scope | Four offenses against persons, public places only, hex-aggregated |
| The lit-and-busy preference is opt-in and bounded | After dark only; at most 10% extra traffic exposure; must improve lighting/foot traffic by ≥ 15% or the default route is kept |
| Honest framing | Scores describe where and when crashes concentrate, not a per-person probability; "traffic risk" and "lower-risk" wording; model card discloses exposure bias and reporting bias |

## 10. Residual risks and follow-ups

- Access-log coordinates are not rounded (section 2).
- Rate limits and caches are per process; scaling past one worker needs a shared store.
- `/openapi.json` is public (no secrets in it, but it documents every endpoint).
- No automated dependency-vulnerability scanning.
- Follow links are bearer URLs: anyone the walker shares them with can see the walk until it ends or expires.
- The exposed key from the masking incident must be confirmed revoked in the provider console (listed as open in `docs/sponsor_checklist.md`).
