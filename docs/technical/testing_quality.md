# Testing and quality

How PathPro is tested, what the suites cover, the numbers measured for this document, and the known gaps. All counts below were produced by running the suites on 2026-09-26 (Apple M1, macOS) against the working tree at commit `f090bd4`.

## 1. Strategy

- **Test first.** Features were built RED → GREEN: a `test:` commit with failing tests, then a `feat:`/`fix:` commit that makes them pass. Of 137 commits, 36 are `test:` commits (13 explicitly marked "(RED)"), 44 `feat:`, 19 `fix:`, 4 `perf:`, 2 `refactor:`, 26 `docs:`, 6 `chore:`.
- **Tests that guard product rules, not just code paths.** The most important tests encode promises made to users:

| Rule | Test |
| --- | --- |
| Factor bars sum exactly to the displayed score | `backend/tests/test_scoring.py::test_attribution_always_sums_exactly` (Hypothesis, 200 examples); `test_api.py::test_segment_detail_factors_sum_to_score`; `test_areas.py::test_area_lookup_factors_sum_to_score` |
| Exported log density equals the model's EB × multiplier / length | `export/assemble._check_identity` (assertion inside every export, tolerance 1e-6); `data/tests/test_temporal.py::test_contributions_sum_to_log_multiplier`; `data/tests/test_factors.py` |
| Routes never exceed the detour budget | `backend/tests/test_router.py::test_pathpro_route_respects_detour_budget`; `test_safety_router.py::test_choose_lit_plan_respects_budget_and_exposure_cap`; `test_modes.py::test_ride_router_uses_mode_speed_and_the_same_detour_rule` |
| Crime never changes a route | `backend/tests/test_safety_router.py::test_crime_counts_never_change_the_route` (crime × 0, × 1, × 1,000) |
| A hex with no reports is never "higher" | `data/tests/test_safety_crime.py::test_posterior_bands_never_mark_a_hex_without_reports_higher` |
| LLM text with an unknown number, a promise, or crime framing is rejected | `backend/tests/test_explain.py` |
| Explanations fall back to the template within the time budget | `test_explain.py::test_timeouts_and_errors_fall_back_to_template_within_budget` |
| UI copy never uses banned framings | `frontend/src/components/safety/copy.test.tsx`; `frontend/e2e/demo.spec.ts` "copy never promises safety" |
| The ride export never changes a walk byte | `data/tests/test_ride_export.py` |
| Share-my-walk tokens never appear in responses; only the owner can update | `backend/tests/test_walks_api.py`, `test_walks_service.py`, `test_walks_repo.py` |
| Deduplication and snapping match golden cases | `data/tests/test_dedupe.py`, `test_snap.py` |
| The offline demo works with the network off | `frontend/e2e/demo.spec.ts` (`context.setOffline(true)`) |

- **Fakes, not live services.** Backend tests use a bundle factory (`backend/tests/bundle_factory.py`, `safety_factory.py`) that writes a small synthetic bundle, an in-memory Mongo collection (`fake_mongo.py`), `respx` for HTTP providers, and a fixed clock. No test calls a paid API; a `network` marker exists for live checks and is not used by default.
- **Frontend.** Vitest + React Testing Library + `vitest-axe` in jsdom; `msw` for HTTP; behaviour-focused queries by role and name. WebGL components (`src/map/**`) and the app shell are excluded from unit coverage and exercised by Playwright.

## 2. Suites and measured results

| Suite | Command | Result | Time |
| --- | --- | --- | --- |
| Data pipeline | `uv run --package pathpulse-data pytest data/tests -q -p no:cacheprovider` | **222 passed** (27 test files) | 42 s |
| Backend API | `uv run --package pathpulse-backend pytest backend/tests -q -p no:cacheprovider` | **277 passed**, 1 warning (Starlette `TestClient` deprecation notice) (26 test files) | 29 s |
| Frontend unit and component | `cd frontend && npx vitest run --coverage` | **541 passed** in 66 test files | 79 s |
| End-to-end (Playwright) | `cd frontend && npx playwright test` | **19 tests defined**: desktop project 16 (`live.spec.ts` 8, `demo.spec.ts` 5, `gps.spec.ts` 3), phone project (Pixel 7) 3 (`mobile.spec.ts`). **Not re-run for this document** (it starts uvicorn and Vite and renders WebGL on SwiftShader). | n/a |
| Total automated tests | | **1,040 unit/integration tests passing + 19 e2e tests** | |

Playwright configuration: `timeout` 90 s, `expect` 20 s, SwiftShader GL flags, `retries: 1` on CI only, traces kept on failure, web servers started for the API (`/healthz`) and Vite.

## 3. Coverage

| Package | Measured | Threshold | Notes |
| --- | --- | --- | --- |
| Backend (`app`) | **91.6%** lines (`--cov=app --cov-config=backend/pyproject.toml`) | 80% (`fail_under`) | Passes |
| Frontend (`src`, excluding map/WebGL shell) | **98.8% lines, 97.4% statements, 92.5% branches, 96.8% functions** | 80 / 80 / 75 / 80 | Passes |
| Data (`pathpulse_data`, package config) | **78.9%** lines (`--cov=pathpulse_data --cov-config=data/pyproject.toml`) | 80% (`fail_under`) | **Below threshold.** `citywide/export.py`, `citywide/features.py`, `citywide/model.py` (City Pulse) are at 0% because they are exercised only by running the pipeline; `export/assemble.py` 49%, `network/graph.py` 48%, `network/bike.py` 67%, `network/coverage.py` 63%, `model/dataset.py` 77%. `data/pyproject.toml` already omits other IO-only CLIs from coverage; the City Pulse modules are not in that omit list. |

Note on the documented command: `uv run --package pathpulse-data pytest data/tests --cov` from the repository root picks up no coverage configuration (the root `pyproject.toml` has none), so it measures test files as well and reports 89%. The package-scoped numbers above are the meaningful ones.

## 4. Static analysis

| Tool | Command | Result |
| --- | --- | --- |
| ruff (lint: E, F, W, I, N, UP, B, SIM, RUF, S, PTH; line length 100) | `uv run ruff check data backend` | **All checks passed** |
| mypy (`strict = true`) | `uv run mypy data/src backend/app` | **47 errors in 26 files** (112 files checked) |
| TypeScript | `cd frontend && npx tsc -b --noEmit` | **Passes** (exit 0) |
| oxlint | `cd frontend && npx oxlint` | Warnings only (for example `react(set-state-in-effect)` in `hooks/useTypewriter.ts`, `react(only-export-components)` in `components/Timeline.tsx`); no errors |
| gitleaks | pre-commit hook; `gitleaks detect` on history | No leaks in history (see [security_privacy.md §8](security_privacy.md#8-secret-handling-and-the-key-masking-incident)) |

### Known mypy errors (pre-existing)

By category: 14 `arg-type`, 13 `no-any-return`, 6 `call-overload`, 5 `index`, 4 `dict-item`, and one each of `unused-ignore`, `type-arg`, `return-value`, `no-untyped-call`, `assignment`. Most are in the data pipeline around pandas and NumPy typing (for example `export/writers.py`, `model/temporal_data.py`, `db/load_tiger.py`). Backend examples:

- `app/main.py:53–58`: `GroqProvider`/`GeminiProvider` are frozen dataclasses whose `name` is read-only, while the `Provider` protocol declares `name` as a settable attribute. Declaring `name` as a read-only property in the protocol would fix it.
- `app/services/geocode.py`: the `params` dict is inferred as `dict[str, object]`.
- `app/tools/record_demo.py`: mixed-type dict literals.

None of these affects runtime behaviour (the test suites pass), but the "mypy clean" goal in the build plan is not met.

## 5. Reviews

Independent reviewer agents were run at milestones, and each review's findings became their own `fix:` commits:

| Review | Agent | Resulting commit |
| --- | --- | --- |
| Model evaluation honesty (spatial-block bootstrap, grouped CV folds, fair temporal baseline, HIN at its own length share) | `ecc:mle-reviewer` | `a2d87d9` |
| Security (rate limits, budgets, worker thread for routing, error envelopes) | `ecc:security-reviewer` | `554600d` |
| Mobile UX redesign (route-metre progress, preview arrival, named GPS starts, status screen) | code review of the redesign | `26010e4` |
| Personal-safety extension (optional export guard, StreetLight error, in-memory walk throttle, day-part literal) | code and security review | `0a046c3` |
| Deploy scripts (system Python under `ProtectHome`, sslip.io HTTPS before DNS, surfacing failures) | found while going live, not an agent review | `47fc47e` |

Workflow per milestone (from `CLAUDE.md`): plan → failing test (commit) → implement (commit) → reviewers → verification loop (ruff, mypy, tsc, lint, tests with coverage, gitleaks) → checkpoint.

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
| Data package coverage 78.9% vs the 80% gate (City Pulse modules untested) | Open |
| 47 mypy strict errors | Open, runtime-neutral |
| Playwright suite not re-run for this document | 19 tests exist; run `npx playwright test` from `frontend/` before a release |
| No CI pipeline in the repository (`.github/` absent); checks run locally and in the pre-commit hook | Open |
| No automated dependency-vulnerability scan | Open |
| Temporal and ride models have no bootstrap intervals on their deviance numbers; City Pulse capture has no interval | Documented in [data_and_models.md](data_and_models.md) |
| Starlette `TestClient` deprecation warning | Cosmetic |
