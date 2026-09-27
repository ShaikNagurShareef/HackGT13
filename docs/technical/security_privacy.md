# Security, privacy, and responsible AI

What PathPro protects, how, and where the controls live in code. Everything below was checked against the code and the live headers of https://pathpro.tech on 2026-09-26.

## 1. Threat model summary

PathPro has no user accounts, no payments, and no personal profiles. The assets worth protecting are small but real:

| Asset | Threat | Main controls |
| --- | --- | --- |
| Sponsor API keys (xAI, Groq, Gemini, ElevenLabs, Backboard, Geoapify, databases, Vultr) | Leak through the browser, git, logs, reprs, or terminal output | Keys only in `backend/.env`; server-side proxying; `SecretStr`; `repr=False` on every client that holds a key; type-only error logging; gitleaks pre-commit hook; masked key helpers (section 8) |
| Paid quotas (LLM, voice, image generation, Ask, memory clones) | Cost abuse by scripted clients | Paid rate-limit class, per-client daily caps, daily budgets, caching, single-flight calls (section 5) |
| A walker's live location (Share my walk) | Hijacking or reading someone else's walk | 128-bit unguessable walk ids, 256-bit owner tokens stored only as SHA-256, constant-time comparison, 6 h TTL, metro-area bounds (section 3) |
| Users' trust in the numbers | Hallucinated or alarming explanations and answers; prompt injection through street names or docs | Evidence-only LLM input, flattened evidence strings, validators, template and fixed fallbacks, banned framings (section 7) |
| Ask PathPro conversations and memory | Reading or continuing someone else's conversation; writing the shared assistant's memory; memory keeping places or routes | HMAC-signed thread and memory tokens with separate purposes, threads bound to their assistant, shared assistant always `Readonly`, opt-in clones with a preference-only fact filter, Forget me (sections 4 and 7.2) |
| Generated street illustrations | A picture read as a real photo or a promise; text, logos, or recognizable faces in it | Server-written prompt without street names, Gemini review before caching, fixed AI-illustration label (section 7.3) |
| Neighbourhoods and the people in them | Stigmatizing areas, demographic proxies, crime-driven routing | No demographic, income, or crime features in any model; crime is display-only with a fairness note; tested (section 9) |
| Service availability | Floods, slow dependencies | Rate limits, timeouts on every call, cooldowns, graceful degradation, a fully offline demo |
| Server | Remote code execution, lateral movement | Loopback-only API behind Caddy, hardened systemd unit, ufw, no shell-outs or dynamic SQL on the request path (section 6) |

Out of scope for a hackathon deployment: DDoS protection beyond the per-client limits, WAF, and multi-region failover.

## 2. Data minimization

| Data | What is kept | What is never kept |
| --- | --- | --- |
| Crash records (pipeline) | Location, timestamp, year, pedestrian/cyclist flags, severity letter, reported light and surface, road names | Names, ages, narratives, map URLs (`PII_COLUMNS` in `ingest/clean.py` are dropped or never selected) |
| Reported crimes (safety layer) | Per H3 res-9 hex × day part counts and bands only | Addresses, report numbers, victim fields, points. The fetch requests only `OccurredFromDate, NIBRS_Offense, LocationType` and geometry; residences, apartments, jails, and shelters are excluded; sex offenses are not included |
| Routing requests | Nothing persisted. The last 512 route results sit in process memory for `/explain` and Ask PathPro | Origin and destination are not written to any database |
| Ask PathPro questions | Sent to Backboard with a server-built context block (street name, score, factors, time, conditions; or route minutes and streets; or an area's score) and kept in that Backboard thread | Coordinates, cell ids, GPS, places, routines. The API never logs question or answer text, tokens, or ids |
| Ask PathPro memory (opt-in only) | A private Backboard assistant clone per browser, written only from plain questions and filtered to stated travel preferences (usual times, travel mode, well-lit or busier streets, accessibility needs); deleted by Forget me, and by `prune_backboard` after 30 days | Places, addresses, streets, routes, names, contact details, the context block. With memory off nothing is written to any assistant memory |
| Ask PathPro tokens in the browser | Thread token in sessionStorage (`pathpro:ask-thread`, this tab); memory token in localStorage (`pathpro:ask-memory:v1`), zod-validated on read | Bare Backboard ids |
| Street illustrations | One image and a check sidecar per segment and image model in `IMAGINE_CACHE_DIR`; file names are built from the integer id and a slugged model name only | Anything about who asked. The prompt comes from model factors only |
| Learned routines | Browser `localStorage` only (`pathpro:routines:v1`, max 200 trips), zod-validated, one tap clears | Nothing is sent to the server |
| Share-my-walk session in the browser | `sessionStorage` only (this tab), never `localStorage` or the URL | |
| Shared walks (Atlas) | Destination label and point, ETA, latest position and accuracy, optional route, status, timestamps, SHA-256 of the owner token | The token itself; any user identity. The TTL index deletes the document 6 h after the last update |
| Community reports (Atlas) | Segment id, one of six fixed categories, street name and point **from the bundle**, confirmation count, timestamps | Free text, reporter identity, the reporter's location. TTL removes a report 14 days after its last confirmation |
| Analytics | None: no analytics or tracking scripts in the SPA, no cookies set by PathPro | |

Access logs (PRD NFR-09): Caddy's JSON access log (`/var/log/caddy/pathpulse.log`) uses a `format filter` that deletes the `lat`, `lon`, `bbox`, `q`, and `t` query parameters and the `Cookie` header before writing. A location lookup is logged as `/api/areas/lookup?cond=live`. Request bodies (route origins and destinations, walk positions) are never logged. The log keeps client IP and user agent for abuse control, and lives only on the VM. Entries written before this filter shipped (Sep 26, 2026) still contain full query strings. uvicorn runs with `--no-access-log` (commit 36372be), so the systemd journal records no request paths or query strings.

## 3. Input validation

Every request body and parameter is a pydantic model or a typed FastAPI parameter; failures become 422 `BAD_REQUEST` without echoing validator details.

| Surface | Validation |
| --- | --- |
| Coordinates | `lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`; Share-my-walk also rejects NaN/Infinity and anything outside a metro-Atlanta box |
| Times | `t`/`depart_at` ≤ 40 chars; `now`, `+Nm`, `+Nh` (≤ 3 digits) or ISO-8601 within 400 days |
| Enums | `cond`, `mode`, `prefer`, `kind`, report `category`, walk `status` are `Literal` types |
| Ids and keys | `seg_id ≥ 0` and range-checked against the bundle; `route_key` `^[0-9a-f]{16}$`; H3 `cell` `^[0-9a-f]{15}$`; `walk_id` ≤ 128 chars and `[A-Za-z0-9_-]{16,64}` before any lookup; owner token 16–128 chars |
| Viewports | `bbox` ≤ 120 chars, four finite ordered numbers, each span ≤ 0.3°; wider boxes are refused rather than truncated |
| Strings | Geocode `q` 1–80 chars; walk destination label 1–120 chars (trimmed); route ≤ 2,000 points; ETA ≤ 12 h; Ask question ≤ 1,000 chars on the wire, then 3–300 characters with no control characters (422 `BAD_QUESTION`); Ask thread and memory tokens ≤ 128 chars, then a strict `<uuid>.<signature>` pattern |
| Ask context | A discriminated union of ids only (`segment`, `route`, `area`) with the same patterns as `/explain` and `/areas`; free text and coordinates are not accepted |
| Unknown fields | `extra="forbid"` on report, walk, Imagine, Ask, and Ask-context request models |
| Server-derived data | Report location and street name come from the bundle, never the client; `/tts` and `/tts/alert` speak only server-generated text; the Grok Imagine prompt and every Ask context block are built on the server from ids |
| Untrusted upstream data | Atlas documents are re-validated on read (`parse_report`, `parse_walk`) and malformed ones skipped; Backboard responses are parsed strictly (ids must be UUIDs, runs must be `COMPLETED`); Grok Imagine bytes must carry a PNG or JPEG signature and be ≤ 8 MB; Gemini's review must match a JSON schema with boolean flags, and only exact planned fix phrases are kept; cached check sidecars are re-parsed strictly; the SPA zod-validates every API response and every browser-storage read |
| Output shape | Separate response models, so tokens and hashes cannot leak into walk responses |

Database access uses parameterized queries (`psycopg` `%s` placeholders in `repositories/history.py`) and structured Mongo filters; no query is built by string concatenation from user input.

## 4. Authentication and authorization

There are no accounts. Two kinds of capability decide what a browser may do.

**Share my walk: "may this client update this shared walk?"**

- `walk_id` = `secrets.token_urlsafe(16)` (128 bits). Anyone with the follow link can **read** the walk; ids are not enumerable.
- `owner_token` = `secrets.token_urlsafe(32)` (256 bits), returned once at creation; the database stores `sha256(token)`; comparison uses `hmac.compare_digest`.
- Updates are conditional on the previous `updated_at` (optimistic concurrency), so racing writes cannot overwrite each other.
- The in-memory update gate records only authenticated, saved updates, so a follower who knows the walk id cannot throttle the walker.

**Ask PathPro: "may this browser continue this conversation or use this memory?"** (`services/ask_threads.py`)

- The browser never sees a bare Backboard id. A token is `<uuid>.<sig>`, where `sig` is the first 32 base64url characters (192 bits) of HMAC-SHA256 over a purpose, a binding, and the canonical UUID, under a server secret (`ASK_THREAD_SECRET`, or 32 random bytes per process when unset).
- **Thread tokens** (purpose `ask-thread`) are bound to the assistant the thread belongs to, so a shared-assistant thread cannot be continued on a memory clone or the reverse. **Memory tokens** (purpose `ask-memory`) name a visitor's clone. The purposes make the two token kinds non-interchangeable.
- Verification checks the pattern, that the UUID is already canonical, and the signature with `hmac.compare_digest`. A token that fails is never forwarded upstream: a bad thread token starts a new thread, a bad memory token means memory is off, and forgetting with a bad token is a silent no-op, so responses never reveal whether a token was valid. A memory token can never select the shared base assistant.
- Tokens, clone ids, and thread ids are never logged.

## 5. Rate limiting and cost control

| Control | Setting | Code |
| --- | --- | --- |
| General limit | 300 requests / min / client (`RATE_LIMIT_PER_MINUTE`) | `middleware.py` |
| Paid/write limit | 30 / min / client on `/explain`, `/geocode`, `/tts` and `/tts/alert`, `POST /ask*`, `POST /imagine*`, `POST /reports`, `POST /walks` (`PAID_RATE_LIMIT_PER_MINUTE`) | same |
| Client identity | `request.client.host` set by uvicorn from `X-Forwarded-For` only for the trusted local proxy (`--forwarded-allow-ips 127.0.0.1`); raw headers from the internet cannot spoof it. IPv6 grouped by /64 | same, `pathpulse.service` |
| Memory bound | Rate-limit state in a TTL cache capped at 50,000 clients | same |
| Per-client daily caps | Grok Imagine 10 new illustrations, Ask 20 questions, 3 memory clones per client address; checked before the shared budget is spent | `ClientDailyLimit` (TTL cache, 50,000 clients) |
| Daily budgets | Explanations 3,000, Geoapify 2,500, each voice 500, Grok Imagine 40 (a redraw after a failed check takes another), Ask 300, memory clones 100 | `DailyBudget` |
| Caching | Explanations (LRU 4,096, keyed by evidence and model version), TTS audio (LRU 256 per voice), navigation alert clips (LRU 512); the SPA prefetches at most 12 alert clips per navigation start, 2 at a time, geocode results (1 h), Grok Imagine images on disk (a cached street is free and uses no cap) | services |
| Single flight | Concurrent requests for one explanation share one LLM call; concurrent taps on one street share one Grok Imagine generation | `ExplainService.explain`, `ImagineService.ensure` |
| Clone housekeeping | `prune_backboard` deletes visitor memory clones older than 30 days | `app/tools/prune_backboard.py` |

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
- `worker-src blob:` and `child-src blob:` are needed by MapLibre's web workers; `media-src blob:` plays TTS audio. Street illustrations load from the same origin (`/api/imagine/...`), so `img-src 'self'` covers them; no provider URL reaches the browser.
- Raw media responses (`/tts` audio, `/imagine/...png`) also send `X-Content-Type-Options: nosniff`, and illustrations are served with the type detected from their magic bytes.
- CORS: explicit origin list, methods `GET, POST, PUT`, header `Content-Type`, no credentials.
- The API binds to 127.0.0.1; ufw exposes only 22, 80, 443. The systemd unit runs as an unprivileged user with `ProtectSystem=strict`, `ProtectHome=true`, `ReadOnlyPaths=/srv/pathpulse`, `NoNewPrivileges`, `PrivateTmp`, an empty capability set, `LockPersonality`, and `RestrictSUIDSGID`. Its one writable path is `CacheDirectory=pathpulse-imagine` (`/var/cache/pathpulse-imagine`, created by systemd and owned by the service user) for Grok Imagine images; cache file names are built from integers and a slugged model name only, so no request text reaches the file system.
- Errors never include stack traces (`unexpected_error_handler`).

## 7. AI guardrails

Three features call generative models: explanations (text and voice), Ask PathPro, and street redesign illustrations. The same principles hold for all three: clients send ids, the server writes every prompt, model output is validated or reviewed before anyone sees it, and failure falls back to fixed, pre-approved content.

### 7.1 Explanations and voice

The chain is xAI Grok → Groq `gpt-oss-120b` → Gemini → Groq `gpt-oss-20b` → deterministic template (`services/explain/`). Every provider gets the same system prompt and the same validator.

| Guardrail | Implementation |
| --- | --- |
| No user text reaches the prompt | The user message is `Evidence (<kind>):\n<JSON>`, built entirely from server data (`evidence.py`) after the client named a segment id or route key (`resolve.py`) |
| Injection through map data | Street names come from OpenStreetMap, which anyone can edit. Every evidence string is flattened before any LLM sees it: control characters and newlines become spaces, runs of whitespace collapse, and each string is cut to 80 characters |
| The LLM never produces a score | Scores, bands, and factor points come from the model; the prompt says "Every number you write must appear in it" |
| Grounding check | `validator.py` extracts every number (after removing evidence strings such as street names and "2020-2024") and every clock time; any number not in the evidence, or a time other than the evidence time label, rejects the text |
| Length and truncation | ≤ 3 sentences, ≤ 420 characters; completions that did not finish normally are rejected |
| Banned framing | Case-insensitive word-boundary match on the `BANNED` tuple in `validator.py`: promise words, crime and violence words, place-stigma phrases, and income, race, and demographic terms (the copy rules in PRD section 7.4) |
| Prompt rules | Say "traffic risk", "lower-risk", "historical crashes"; never mention people, neighborhoods, or demographics; at most three factors and one action; ride modes say "riding" |
| Fallback | Any failure, timeout, or rejection moves to the next provider; the template is always valid and is not cached (so a transient outage does not stick) |
| Voice | `/tts` speaks only text the server produced for the same request, and `/tts/alert` only the line the server writes from a cached route's alert stretch ("High traffic risk ahead." plus up to three cleaned street names); both bodies are ids only (`/tts/alert` forbids extra fields), through Grok Voice or ElevenLabs |
| Community reports | Never included in evidence |

### 7.2 Ask PathPro

| Guardrail | Implementation |
| --- | --- |
| Grounded in project documents | The Backboard assistant answers by retrieval over six documents (model card, metrics, safety sources, decision log, data and models, judge Q&A) and five read-only facts; its system prompt forbids outside knowledge, invented scores, and describing any area by crime |
| Context from ids only | The question may carry a server-built evidence block (street, route, City Pulse area, or live conditions). The client sends ids; coordinates and cell ids are never sent upstream. The block is marked as data for this question only, and the fact-extraction prompt refuses to keep anything inside it |
| Every number sourced | `ask_validation_errors` accepts a number only if it appears in the corpus files (read from disk at startup; fail closed when missing), in the context evidence, or in the question itself |
| No links out | Links, domains, and email addresses are rejected, except `pathpro.tech` and the six corpus file names; source links are built by the server from an allow-list, never taken from the answer |
| On topic, short | At least one PathPro term; ≤ 140 words and ≤ 1,000 characters |
| Framing | The explanation validator's banned words apply, except that answers may name crime data and the personal-safety layer in order to explain how they are (not) used; extra place-stigma phrases are banned; income and demographics may appear only in a sentence that says they are not used; crime named next to routing, scores, cost, or the model must be negated |
| Fallback | A rejected answer, an upstream error, the 12 s timeout, or a spent budget returns one fixed answer that points to the model card. Raw answers are never shown or logged; the log records only the rejection categories |
| Shared memory is read-only | Every call to the shared assistant uses memory `Readonly`; only an opted-in visitor's own clone uses `Auto`, and only for plain questions |
| Memory content | The clone's structured fact-extraction prompt (verified live) keeps only stated travel preferences and returns `{"facts": []}` for places, addresses, and context blocks |

### 7.3 Street redesign illustrations

| Guardrail | Implementation |
| --- | --- |
| Server-written prompt | Built from the segment's traffic-risk factors and road class at a fixed reference hour; no street name, place, or user text. The prompt asks for no text, words, logos, or lettered signs |
| Independent review | Gemini (`GEMINI_CHECK_MODEL`) reviews each picture before it is cached: which planned fixes are visible (exact phrases only), and whether it shows readable text or logos, or an identifiable face. Its instruction says to ignore any writing inside the image that looks like instructions |
| Reject, retry once | A flagged picture is redrawn once; a second flag returns `IMAGINE_REJECTED` and nothing is stored |
| Unchecked is disclosed | When Gemini is unavailable the picture is kept but `check` is null, so the UI shows no "Checked by Gemini" line |
| Labeled | Always shown as "AI illustration of evidence-based street fixes by Grok Imagine — not a real photo"; the picture never changes a score |
| Bounded | Paid rate limit, 10 new pictures per client address and 40 in total per day, single flight per street, 8 MB cap and image-signature check |

UI copy is held to the same rules by tests: `frontend/src/components/safety/copy.test.tsx` renders every personal-safety surface and asserts none contains a banned product-copy word; `frontend/e2e/demo.spec.ts` checks the rendered demo page ("copy never promises safety").

## 8. Secret handling and the key-masking incident

- **Where secrets live.** `backend/.env` only (gitignored; `.env.example` lists names). On the VM the file is streamed with `umask 077` and set to mode 0600.
- **Never in the browser.** Geoapify, xAI (Grok chat, voice, Imagine), Groq, Gemini, ElevenLabs, and Backboard calls are all made by the API.
- **Never in logs or reprs.** Settings use `SecretStr`; every client dataclass that holds a key (`GrokProvider`, `GroqProvider`, `GeminiProvider`, `GeminiImageCheck`, `Backboard`) declares it `field(repr=False)`; failures log `type(exc).__name__` only (exception text from database drivers and HTTP clients can echo a connection string or URL); `httpx` logging is raised to WARNING because Geoapify takes its key as a query parameter. Keys travel only in headers for xAI, Groq, ElevenLabs, Gemini (`x-goog-api-key`), and Backboard (`X-API-Key`).
- **Operator tools.** `app.tools.check_keys` verifies each key with one free call (for xAI and Groq a model listing, never a paid generation) and prints only OK/MISSING/FAIL with a short note. `app.tools.setup_backboard` prints only the new assistant id (not a secret) and document statuses; `app.tools.prune_backboard` prints only counts. The key-capture helpers write matching strings straight to `backend/.env` (`deploy/capture_keys.py` also recognizes `XAI_API_KEY` by its `xai-` prefix and `BACKBOARD_API_KEY` only when copied as `BACKBOARD_API_KEY=...`).
- **Token secret.** `ASK_THREAD_SECRET` signs Ask thread and memory tokens. It is optional: when unset, a random per-process secret is used, which works but resets conversations and memory tokens on restart.

**What the API logs.** uvicorn's access log is off (`--no-access-log` in the unit), so no request paths or query strings reach the journal. The application writes only warnings that carry exception type names and short reason codes only: which explanation provider failed or which rule rejected its output, `ask context dropped: <code>`, `ask answer withheld by validator: <categories>`, `ask backboard unavailable: <type>`, `ask memory clone failed: <type>`, `imagine failed: <type>`, `imagine illustration flagged by check (attempt n)`, `imagine check unavailable: <type>`. Question text, answers, prompts, tokens, thread and clone ids, and keys are never logged. Caddy's access log is filtered as described in section 2.

**Incident (commit `41dd776`, Sat 2026-09-26 11:02 ET).** The browser helper that saved newly created sponsor keys into `backend/.env` masked key-like strings in its own terminal output with a word-boundary regular expression. When the output was JSON, an escaped newline (`\n`) sat directly against a key, the word boundary did not match, and one key was printed unmasked in a local terminal session. It was never committed or deployed. Fix: JSON output is now decoded and each string value is masked individually, and non-JSON output has escaped newlines expanded before masking. The exposed key was flagged for revocation in `docs/sponsor_checklist.md` (the deploy uses a separate, newly created key). Lesson recorded: mask decoded values, not serialized text.

**Scanning.**

- `.pre-commit-config.yaml` runs **gitleaks** (v8.21.2) on every commit, plus ruff, ruff-format, `check-added-large-files` (5 MB), `check-merge-conflict`, and `end-of-file-fixer`. The hook is installed in this clone (`.git/hooks/pre-commit`).
- `gitleaks detect` over the full history (185 commits scanned on 2026-09-26, gitleaks 8.30.1): **2 findings, both false positives**: the placeholder string `xai-secret` passed to `check_xai` in `backend/tests/test_grok.py` (lines 175–176). No real key has been committed.
- `gitleaks dir .` over the working tree flags only `backend/.env` (the intended, gitignored secrets file) and the same test placeholder.
- Dependency pinning: `uv.lock` (Python, installed with `--frozen` on the VM) and `package-lock.json` (installed with `npm ci`). No automated vulnerability scanner (for example `pip-audit` or `npm audit` in CI) is configured.

## 9. Fairness safeguards

| Safeguard | Evidence |
| --- | --- |
| No demographic, income, race, or crime features in the traffic models | Feature list in `model/dataset.py`; ARC income, race, and environmental-justice flags are never read (`network/features.ARC_STRUCTURAL`); the ARC baseline is labelled "demographic flags removed" |
| Crime never enters routing | `EdgeSignals` (the only safety input to the router) holds lighting and activity codes, no crime; `backend/tests/test_safety_router.py::test_crime_counts_never_change_the_route` builds bundles with crime counts × 0, × 1, × 1,000 and asserts identical plans for both route preferences |
| Crime never enters explanations | Evidence builders read only traffic-model output; the validator also rejects crime vocabulary |
| Ask PathPro never frames places by crime | System prompt rule, plus the validator's crime-framing check (place-stigma phrases, and crime next to routing, scores, or the model without a negation); a read-only fact in the assistant states that crime data is informational only |
| Illustrations do not depict identifiable people | Gemini rejects pictures with identifiable faces; the prompt names no street or place |
| No stigma from empty data | Crime bands use an exposure-normalized Empirical-Bayes posterior; a hex with zero reports can never be "higher" (`safety/banding.py`, tested in `data/tests/test_safety_crime.py`) |
| Unknown is not bad | Unknown lighting is never treated as unlit; unknown activity is neutral in routing |
| Always-on context | The fairness note appears wherever crime counts do |
| Narrow crime scope | Four offenses against persons, public places only, hex-aggregated |
| The lit-and-busy preference is opt-in and bounded | After dark only; at most 10% extra traffic exposure; must improve lighting/foot traffic by ≥ 15% or the default route is kept |
| Honest framing | Scores describe where and when crashes concentrate, not a per-person probability; "traffic risk" and "lower-risk" wording; model card discloses exposure bias and reporting bias |

## 10. Residual risks and follow-ups

- Client IPs and user agents remain in the access log, and entries written before the Sep 26, 2026 filter still hold full query strings (section 2).
- Journal entries written before `--no-access-log` shipped (Sep 26, 2026, late evening) may still hold full query strings from uvicorn's access log; they age out with journald rotation. Request bodies (route endpoints, walk positions, Ask questions) were never logged.
- Rate limits and caches are per process; scaling past one worker needs a shared store.
- `/openapi.json` is public (no secrets in it, but it documents every endpoint).
- No automated dependency-vulnerability scanning.
- Follow links are bearer URLs: anyone the walker shares them with can see the walk until it ends or expires.
- Ask PathPro questions, answers, and context blocks are stored in Backboard threads in the project's Backboard account; the code has no thread cleanup (only clones are pruned), so threads persist until deleted there. Memory tokens in localStorage are bearer capabilities for that browser's clone.
- Evidence blocks, questions, and generated pictures are processed by third parties (xAI, Groq, Google, ElevenLabs, Backboard) under their own retention terms.
- Without `ASK_THREAD_SECRET`, a restart invalidates every thread and memory token (clones then become orphans until `prune_backboard` removes them).
- The Grok Imagine cache has no expiry; images are removed only by clearing `IMAGINE_CACHE_DIR`.
- The Ask corpus is uploaded once by `setup_backboard`, while the allowed-number set is read from `docs/` at every start; editing a corpus document without re-running setup can make correct answers fail validation (they then fall back).
- The exposed key from the masking incident must be confirmed revoked in the provider console (listed as open in `docs/sponsor_checklist.md`).
