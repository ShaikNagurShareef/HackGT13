# PathPro technical documentation

**PathPro** ([pathpro.tech](https://pathpro.tech)) forecasts pedestrian and cyclist traffic risk for every street in the City of Atlanta by hour and weather, and plans lower-risk walking and riding routes with grounded explanations. Built by team **CodingClaws** (Nagur Shareef Shaik, Sahith Reddy Thummala, Pranav Nagothu, Geethanjali Nagaboina) at HackGT 13.

These documents describe what the code in this repository does, as of model bundle `pp-20260926-1902-f49c0d2`. A combined PDF is in [pathpro_technical_docs.pdf](pathpro_technical_docs.pdf).

| Document | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | Context and container diagrams, backend layers, request flows (route, explanation, Share my walk, offline demo), walk vs ride bundles, the personal-safety layer, and how each dependency degrades. |
| [data_and_models.md](data_and_models.md) | Data sources with URLs, ingest (clean, dedupe, snap), networks, features, the GLM + monotone LightGBM + Empirical Bayes spatial model, the temporal model, exact factor attribution, City Pulse, the ride model, the safety layer, evaluation tables with confidence intervals, bundle layout, and rebuild commands. |
| [api_reference.md](api_reference.md) | Every endpoint with parameters, limits, response schemas, error codes, rate-limit class, and trimmed real responses; the envelope, CORS, and rate limits. |
| [deployment_operations.md](deployment_operations.md) | Environments, environment variable names, Vultr provisioning, the clean-worktree deploy, Caddy and systemd hardening, DNS, Atlas and Tiger Data setup, health checks, logs, rollback, cost, and a runbook. |
| [security_privacy.md](security_privacy.md) | Threat model, data minimization, input validation, rate limiting, browser hardening, LLM guardrails, secret handling and the key-masking incident, scanning, and fairness safeguards. |
| [testing_quality.md](testing_quality.md) | Test strategy, measured suite counts and coverage, static analysis results, reviews, a latency sample, and known issues. |

## Diagrams

Each diagram is a Mermaid block in its document (rendered by GitHub) and a 2× PNG in [img/](img/):

| PNG | Diagram |
| --- | --- |
| [a1_context.png](img/a1_context.png) | System context (C4 level 1) |
| [a2_containers.png](img/a2_containers.png) | Containers (C4 level 2) |
| [a3_route_sequence.png](img/a3_route_sequence.png) | Plan-a-route sequence |
| [a4_explain_sequence.png](img/a4_explain_sequence.png) | "Why?" explanation chain |
| [a5_share_sequence.png](img/a5_share_sequence.png) | Share my walk |
| [a6_demo_flow.png](img/a6_demo_flow.png) | Offline demo transport |
| [a7_multimode.png](img/a7_multimode.png) | Walk and ride models in one bundle |
| [a8_safety_flow.png](img/a8_safety_flow.png) | Personal-safety data flow |
| [d1_pipeline.png](img/d1_pipeline.png) | Data pipeline |
| [d2_model.png](img/d2_model.png) | Model composition |
| [d3_lineage.png](img/d3_lineage.png) | Bundle lineage |
| [o1_deploy.png](img/o1_deploy.png) | Production deployment topology |

## Key numbers

| Measure | Value |
| --- | --- |
| Walk model, 2024 holdout (543 pedestrian crashes) | 74.3% of crashes on the top 10% of street length, 95% CI [70.5, 78.3]; City High Injury Network 53.8%; past crashes 49.8% |
| Ride model, 2024 holdout (174 cyclist crashes) | 69.9% [64.0, 76.1]; HIN 43.6%; past cyclist crashes 30.4% |
| City Pulse, 2024 | 74.5% of crashes in the top 10% of 3,537 hexes |
| Coverage | 49,915 road segments; 84,758-node walk graph; 49,824-node bike graph |
| Tests (measured 2026-09-26) | data 222, backend 277, frontend 542 passing; 19 Playwright end-to-end tests defined |

Related project documents: [model card](../model_card.md), [safety sources](../safety_sources.md), [process notes](../process/process_notes.md), [PRD](<../../Requirements (PRD).md>).

## Regenerating the diagrams and PDF

The PNGs and the PDF were produced with Playwright's Chromium (from `frontend/`), loading Mermaid 11 from `cdn.jsdelivr.net`: each Mermaid block is rendered to SVG and screenshotted at device scale factor 2; the PDF is the six documents converted to HTML with print CSS, the Mermaid blocks replaced by these PNGs, and printed with `page.pdf()`.
