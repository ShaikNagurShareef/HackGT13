# Testing and quality

How PathPro is tested, what the suites cover, the numbers measured for this document, and the known gaps. All counts below were produced by running the suites on 2026-09-26 (Apple M1, macOS) against `main`: data at commit `0352f21`, backend and frontend re-run at `d4af114` (Grok, Grok Voice navigation alerts, Grok Imagine and its Gemini check, and Ask PathPro with memory included).

## 1. Strategy

- **Test first.** Features were built RED → GREEN: a `test:` commit with failing tests, then a `feat:`/`fix:` commit that makes them pass. Of the first 193 commits on `main`, 54 are `test:` commits (13 explicitly marked "(RED)"), 53 `feat:`, 28 `fix:`, 4 `perf:`, 3 `refactor:`, 45 `docs:`, 6 `chore:`. Every Grok, Grok Voice alert, Grok Imagine, Gemini-check, and Ask PathPro feature landed as a `test:` commit followed by its `feat:` or `fix:` commit.
- **Tests that guard product rules, not just code paths.** The most important tests encode promises made to users:

| Rule | Test |
| --- | --- |
| Factor bars sum exactly to the displayed score | `backend/tests/test_scoring.py::test_attribution_always_sums_exactly` (Hypothesis, 200 examples); `test_api.py::test_segment_detail_factors_sum_to_score`; `test_areas.py::test_area_lookup_factors_sum_to_score` |
| Exported log density equals the model's EB × multiplier / length | `export/assemble._check_identity` (assertion inside every export, tolerance 1e-6); `data/tests/test_temporal.py::test_contributions_sum_to_log_multiplier`; `data/tests/test_factors.py` |
| Routes never exceed the detour budget | `backend/tests/test_router.py::test_pathpro_route_respects_detour_budget`; `test_safety_router.py::test_choose_lit_plan_respects_budget_and_exposure_cap`; `test_modes.py::test_ride_router_uses_mode_speed_and_the_same_detour_rule` |
| Crime never changes a route | `backend/tests/test_safety_router.py::test_crime_counts_never_change_the_route` (crime × 0, × 1, × 1,000) |
| A hex with no reports is never "higher" | `data/tests/test_safety_crime.py::test_posterior_bands_never_mark_a_hex_without_reports_higher` |
| LLM text with an unknown number, a promise, or crime framing is rejected | `backend/tests/test_explain.py` |
| Navigation alerts speak only server-written text, never a client's; unknown routes or alerts are 404; the voice falls back Grok → ElevenLabs → 503 | `test_tts_alert.py::test_alert_endpoint_never_accepts_client_text`, `test_alert_endpoint_unknown_route_or_alert_is_404`, `test_alert_endpoint_falls_back_to_elevenlabs_then_503`, `test_alert_text_cleans_street_names_from_the_map` |
| Grok is first in the explanation chain only when its key is set; voice falls back Grok → ElevenLabs; `/tts` speaks only the server's text; no provider repr shows its key | `test_grok.py::test_provider_order_puts_grok_first_only_with_a_key`, `test_voice_chain_falls_back_from_grok_to_elevenlabs`, `test_tts_endpoint_speaks_only_the_server_explanation_with_grok`, `test_provider_repr_never_shows_the_api_key` |
| Street names are flattened before any LLM sees them | `test_explain_resolve.py::test_street_names_are_cleaned_before_reaching_any_llm` |
| Grok Imagine accepts no prompt text and its plan never carries names or banned copy | `test_imagine.py::test_imagine_rejects_user_supplied_prompt_text`, `test_plan_never_carries_names_or_banned_copy` |
| One client cannot spend the whole Imagine budget; cached pictures cost nothing | `test_imagine.py::test_one_client_cannot_spend_the_whole_daily_budget`, `test_imagine_daily_budget_is_enforced_but_cache_still_serves` |
| A picture Gemini flags is redrawn once, then rejected and never cached; Gemini down means unchecked, not blocked | `test_imagine_check.py::test_flagged_image_is_retried_once_then_rejected_and_not_cached`, `test_gemini_down_still_caches_the_image_unchecked` |
| Ask PathPro answers quote only sourced numbers, carry no links, stay on topic, and never frame places by crime | `test_ask.py::test_validator_rejects_invented_numbers`, `test_validator_rejects_links_domains_and_emails`, `test_validator_rejects_off_topic_answers`, `test_validator_rejects_crime_framing` |
| No coordinates ever reach Backboard | `test_ask_context.py::test_no_coordinates_ever_reach_backboard` |
| Rejected answer text, tokens, and clone ids are never logged | `test_ask.py::test_rejected_answer_text_is_never_logged`, `test_thread_tokens_are_never_logged`; `test_ask_memory.py::test_memory_tokens_and_clone_ids_are_never_logged` |
| Forged thread tokens are never forwarded; thread and memory tokens are not interchangeable | `test_ask.py::test_unverified_thread_is_never_forwarded_upstream`; `test_ask_memory.py::test_thread_and_memory_tokens_are_not_interchangeable`, `test_a_base_thread_is_not_continued_on_the_clone` |
| The shared assistant is read-only; a clone writes memory only from plain questions; memory keeps only stated preferences | `test_ask.py::test_ask_new_thread_uses_readonly_memory`; `test_ask_memory.py::test_valid_memory_token_uses_the_clone_with_auto_memory`, `test_context_questions_never_write_memory_even_on_a_clone`; `test_backboard_setup.py::test_fact_extraction_keeps_only_stated_preferences` |
| Forget me is idempotent and never calls upstream for an invalid token | `test_ask_memory.py::test_forget_an_already_deleted_clone_is_fine`, `test_forget_with_an_invalid_token_never_calls_upstream` |
| Explanations fall back to the template within the time budget | `test_explain.py::test_timeouts_and_errors_fall_back_to_template_within_budget` |
| UI copy never uses banned framings | `frontend/src/components/safety/copy.test.tsx`; `frontend/e2e/demo.spec.ts` "copy never promises safety" |
| The ride export never changes a walk byte | `data/tests/test_ride_export.py` |
| Share-my-walk tokens never appear in responses; only the owner can update | `backend/tests/test_walks_api.py`, `test_walks_service.py`, `test_walks_repo.py` |
| Deduplication and snapping match golden cases | `data/tests/test_dedupe.py`, `test_snap.py` |
| The offline demo works with the network off | `frontend/e2e/demo.spec.ts` (`context.setOffline(true)`) |

- **Fakes, not live services.** Backend tests use a bundle factory (`backend/tests/bundle_factory.py`, `safety_factory.py`) that writes a small synthetic bundle, an in-memory Mongo collection (`fake_mongo.py`), `respx` for every HTTP provider (xAI, Groq, Gemini, ElevenLabs, Backboard, Geoapify, Open-Meteo), a temporary directory for the image cache, and a fixed clock. No test calls a paid API; a `network` marker exists for live checks and is not used by default.
- **Frontend.** Vitest + React Testing Library + `vitest-axe` in jsdom; `msw` for HTTP; behaviour-focused queries by role and name. WebGL components (`src/map/**`) and the app shell are excluded from unit coverage and exercised by Playwright.

## 2. Suites and measured results

| Suite | Command | Result | Time |
| --- | --- | --- | --- |
| Data pipeline | `uv run --package pathpulse-data pytest data/tests -q -p no:cacheprovider --cov=pathpulse_data --cov-config=data/pyproject.toml` | **237 passed** (30 test files) | 39 s |
| Backend API | `uv run --package pathpulse-backend pytest backend/tests -q -p no:cacheprovider --cov=app --cov-config=backend/pyproject.toml` | **655 passed**, 1 warning (Starlette `TestClient` deprecation notice) (36 test files) | 25 s |
| Frontend unit and component | `cd frontend && npx vitest run --coverage` | **640 passed** in 72 test files | 21 s |
| End-to-end (Playwright) | `cd frontend && npx playwright test` | **19 tests defined**: desktop project 16 (`live.spec.ts` 8, `demo.spec.ts` 5, `gps.spec.ts` 3), phone project (Pixel 7) 3 (`mobile.spec.ts`). **Not re-run for this document** (it starts uvicorn and Vite and renders WebGL on SwiftShader). | n/a |
| Total automated tests | | **1,532 unit/integration tests passing + 19 e2e tests defined (1,551)** | |

Playwright configuration: `timeout` 90 s, `expect` 20 s, SwiftShader GL flags, `retries: 1` on CI only, traces kept on failure, web servers started for the API (`/healthz`) and Vite.

## 3. Coverage

| Package | Measured | Threshold | Notes |
| --- | --- | --- | --- |
| Backend (`app`) | **93.8%** lines (`--cov=app --cov-config=backend/pyproject.toml`) | 80% (`fail_under`) | Passes. New modules: `api/ask.py`, `api/ask_context.py`, `api/imagine.py`, `explain/resolve.py`, `services/alert_voice.py` 100%; `services/imagine.py` 98%, `ask.py` 98%, `ask_memory.py`, `ask_threads.py`, `ask_corpus.py` 96%, `imagine_check.py`, `backboard.py` 95% |
| Frontend (`src`, excluding map/WebGL shell) | **98.7% lines, 97.2% statements, 92.5% branches, 96.6% functions** | 80 / 80 / 75 / 80 | Passes |
| Data (`pathpulse_data`, package config) | **89.1%** lines (`--cov=pathpulse_data --cov-config=data/pyproject.toml`) | 80% (`fail_under`) | Passes since City Pulse tests with synthetic fixtures landed (`c7599d3`): `citywide/features.py`, `hexgrid.py`, `model.py` 100%, `citywide/export.py` 70%. Lowest remaining: `network/graph.py` 48%, `export/assemble.py` 49%, `network/coverage.py` 63%, `network/bike.py` 67% (network and file I/O paths exercised by running the pipeline). |

Note on the documented command: `uv run --package pathpulse-data pytest data/tests --cov` from the repository root picks up no coverage configuration (the root `pyproject.toml` has none), so it measures test files as well. The package-scoped numbers above are the meaningful ones.

## 4. Static analysis

| Tool | Command | Result |
| --- | --- | --- |
| ruff (lint: E, F, W, I, N, UP, B, SIM, RUF, S, PTH; line length 100) | `uv run ruff check data backend` | **All checks passed** |
| mypy (`strict = true`) | `uv run mypy data/src backend/app` | **44 errors in 25 files** (127 files checked); none in the Grok, Imagine, or Ask modules |
| TypeScript | `cd frontend && npx tsc -b --noEmit` | **Passes** (exit 0) |
| oxlint | `cd frontend && npx oxlint` | Warnings only (for example `react(set-state-in-effect)` in `hooks/useTypewriter.ts`, `react(only-export-components)` in `components/Timeline.tsx`); no errors |
| gitleaks | pre-commit hook; `gitleaks detect` on history | No leaks in history (see [security_privacy.md §8](security_privacy.md#8-secret-handling-and-the-key-masking-incident)) |

### Known mypy errors (pre-existing)

By category: 13 `no-any-return`, 11 `arg-type`, 6 `call-overload`, 5 `index`, 4 `dict-item`, and one each of `unused-ignore`, `type-arg`, `return-value`, `no-untyped-call`, `bool`, `assignment`. Most are in the data pipeline around pandas and NumPy typing (for example `export/writers.py`, `model/temporal_data.py`, `db/load_tiger.py`). Backend examples:

- `app/services/safety.py`, `app/services/segments.py`: plain `str` passed where a `Literal` is expected (`day_part`, `source`), and one unused `type: ignore`.
- `app/domain/router.py`, `app/domain/scoring.py`, `app/repositories/artifacts.py`: NumPy functions returning `Any`.
- `app/services/geocode.py`, `app/services/weather.py`: the `params` dict is inferred as `dict[str, object]`.
- `app/tools/record_demo.py`: mixed-type dict literals.

None of these affects runtime behaviour (the test suites pass), but the "mypy clean" goal in the build plan is not met.

## 5. Reviews

Independent reviewer agents were run at milestones, and each review's findings became their own `fix:` commits:

| Review | Agent | Resulting commit |
| --- | --- | --- |
| Model evaluation honesty (spatial-block bootstrap, grouped CV folds, fair temporal baseline, HIN at its own length share) | ML review | `a2d87d9` |
| Security (rate limits, budgets, worker thread for routing, error envelopes) | Security review | `554600d` |
| Mobile UX redesign (route-metre progress, preview arrival, named GPS starts, status screen) | code review of the redesign | `26010e4` |
| Personal-safety extension (optional export guard, StreetLight error, in-memory walk throttle, day-part literal) | code and security review | `0a046c3` |
| Deploy scripts (system Python under `ProtectHome`, sslip.io HTTPS before DNS, surfacing failures) | found while going live, not an agent review | `47fc47e` |
| Grok features (per-client Imagine cap, API keys hidden from provider reprs, `nosniff` on TTS audio) | follow-up hardening, test first (`16bea62`) | `35bf129` |
| Grok Imagine on a hardened unit (writable systemd `CacheDirectory` under `ProtectSystem=strict`) | found while deploying | `4151c86` |
| Ask PathPro (per-client cap, HMAC-signed thread tokens, link and topicality checks) | follow-up hardening, test first (`4bce5d1`) | `ab79eb3` |
| Ask PathPro memory (memory written only from plain questions, street names cleaned before any LLM, demographics only when negated) | follow-up hardening, test first (`eed6059`, `64dbc57`) | `0c81113` |
| Backboard fact extraction (structured `{"facts": [...]}` prompt, verified against the live service) | live verification, test first (`5cbb9fd`) | `0352f21` |

Workflow per milestone: plan → failing test (commit) → implement (commit) → reviewers → verification loop (ruff, mypy, tsc, lint, tests with coverage, gitleaks) → checkpoint.

## 6. Latency sample

Measured for this document, in-process with FastAPI's `TestClient` on an Apple M1 laptop, real bundle `pp-20260926-1902-f49c0d2`, no API keys and no database (so no Atlas report lookup), `cond: "dry"`, depart Friday 22:30. Random origins around Georgia Tech; successful plans only.

| Mode | Trips | p50 | p95 | Max |
| --- | --- | --- | --- | --- |
| Walk (0.8–3 km) | 40 | 47 ms | 78 ms | 246 ms |
| Bike (2–8 km) | 40 | 40 ms | 85 ms | 135 ms |

Bundle load at startup: 0.6 s. This excludes network time and the production VM's slower single vCPU, so treat it as a lower bound; the PRD target is p95 < 1.5 s end to end (NFR-03). Earlier measurements recorded in the repository: route planning p95 fell from 1.95 s to 0.26 s after the citywide router refactor (`c8d5e8f`), and default plus lit-and-busy plans together ran p50 154 ms, p95 283 ms on 40 random night trips (`docs/safety_sources.md`).

## 7. Known issues and gaps

| Item | Status |
| --- | --- |
| Data package coverage below the 80% gate | Closed: 89.1% after the City Pulse tests (`c7599d3`) |
| 44 mypy strict errors | Open, runtime-neutral |
| Playwright suite not re-run for this document | 19 tests exist; run `npx playwright test` from `frontend/` before a release. None of them covers Ask PathPro or Grok Imagine (both hidden in the offline demo and dependent on paid providers); those are covered by component tests with a mocked API |
| Live provider behaviour (xAI, Gemini check, Backboard) | Checked by hand against the live services (for example the Backboard fact format, `0352f21`, and the Gemini check model, `09ea075`); no automated live test, by design |
| No CI pipeline in the repository (`.github/` absent); checks run locally and in the pre-commit hook | Open |
| No automated dependency-vulnerability scan | Open |
| Temporal and ride models have no bootstrap intervals on their deviance numbers; City Pulse capture has no interval | Documented in [data_and_models.md](data_and_models.md) |
| Starlette `TestClient` deprecation warning | Cosmetic |
