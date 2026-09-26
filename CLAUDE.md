# PathPro

Pedestrian traffic-risk forecasting map and risk-aware walking router for Atlanta (HackGT 13).
Source of truth for scope: `Requirements (PRD).md`. Build plan: see `docs/architecture.md`.

## Layout
- `data/` — uv package `pathpulse_data`: fetch → clean/dedupe/snap → network features → model (SPF ensemble + EB + temporal GLM) → export frames/bundle → load Tiger Data.
- `backend/` — FastAPI app `app`: routes, segment detail, areas, explanations (Groq → Gemini → template), live conditions, geocode, TTS.
- `frontend/` — Vite + React + TS, MapLibre + deck.gl, zod-validated API client.
- `artifacts/<model_version>/` — exported bundle (frames, geometry, graph, quantiles, manifest). Only `artifacts/demo/` is committed.

## Commands
- Python tests: `uv run --package pathpulse-data pytest data/tests --cov` and `uv run --package pathpulse-backend pytest backend/tests --cov`
- Lint/types: `uv run ruff check data backend && uv run mypy data/src backend/app`
- Frontend: `cd frontend && npm run test -- --coverage && npm run build && npx playwright test`
- Run API: `cd backend && uv run uvicorn app.main:create_app --factory --reload`

## Non-negotiables (from PRD)
- Say "traffic risk", "lower-risk", "well-lit", "busier streets", "help points", "reported crimes against persons". Never "safe", "safest", "unsafe", "dangerous area/neighborhood", "bad area", "guaranteed".
- The LLM never produces a risk number; explanation text is validated against the evidence payload. LLM explanations stay about traffic risk (the validator still rejects crime framing).
- No demographic or income features anywhere. No crime features in the traffic-risk model or in routing cost.
- Personal-safety layer (user decision, 2026-09-26): safety signals (lighting, foot traffic, help points) may shape the optional "Well-lit & busier" route preference after dark; APD crimes against persons are informational only, aggregated to H3 hexes by day-part, always shown with the fairness note, never used to route.
- Demo path (`?demo=1`) must work offline; the DB is never on the hot path.
- API keys live only in `backend/.env`; never in the frontend or git.

## ECC skill map
| Files | Skills / agents |
| --- | --- |
| `data/**/model/**`, `data/**/timeseries/**` | `ecc:mle-workflow`, agent `ecc:mle-reviewer` |
| `data/**`, `backend/**/*.py` | `ecc:python-patterns`, `ecc:python-testing`, `ecc:tdd-workflow`, agent `ecc:python-reviewer` |
| `backend/app/**` | `ecc:fastapi-patterns`, `ecc:api-design`, agent `ecc:fastapi-reviewer` |
| `backend/app/services/explain/**` | `ecc:cost-aware-llm-pipeline`, agent `ecc:security-reviewer` |
| `data/sql/**`, `data/**/db/**` | `ecc:postgres-patterns`, agent `ecc:database-reviewer` |
| `frontend/src/**` | `ecc:react-patterns`, `ecc:frontend-a11y`, `ecc:react-testing`, agent `ecc:react-reviewer` |
| `frontend/e2e/**` | `ecc:e2e-testing`, agent `ecc:e2e-runner` |
| `deploy/**` | `ecc:deployment-patterns` |

Workflow per milestone: plan → failing test (commit) → implement (commit) → reviewers → `verification-loop` → checkpoint.
Commits: conventional (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`, `perf:`).
