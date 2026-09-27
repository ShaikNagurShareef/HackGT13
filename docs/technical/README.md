# PathPro technical documentation

**PathPro** ([pathpro.tech](https://pathpro.tech)) forecasts pedestrian and cyclist traffic risk for every street in the City of Atlanta by hour and weather, and plans lower-risk walking and riding routes with grounded explanations, read aloud on request, and spoken navigation alerts. It can also illustrate evidence-based fixes for a street (Grok Imagine, checked by Gemini) and answer questions about itself and what is on screen (Ask PathPro on Backboard). A solo build by Nagur Shareef Shaik (team name Coding Claws, Georgia State University) at HackGT 13.

These documents describe what the code on `main` does, as of model bundle `pp-20260926-1902-f49c0d2` and commit `0352f21`. A combined PDF is in [pathpro_technical_docs.pdf](pathpro_technical_docs.pdf).

| Document | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | Context and container diagrams, backend layers, request flows (route, explanation and voice, Share my walk, offline demo, street redesign illustrations, Ask PathPro and its opt-in memory), walk vs ride bundles, the personal-safety layer, and how each dependency degrades. |
| [data_and_models.md](data_and_models.md) | Data sources with URLs, ingest (clean, dedupe, snap), networks, features, the GLM + monotone LightGBM + Empirical Bayes spatial model, the temporal model, exact factor attribution, City Pulse, the ride model, the safety layer, evaluation tables with confidence intervals, bundle layout, and rebuild commands. |
| [api_reference.md](api_reference.md) | Every endpoint (including `/tts/alert`, `/imagine/*`, and `/ask*`) with parameters, limits, response schemas, error codes, rate-limit class, and sample responses; the envelope, CORS, rate limits, and daily budgets. |
| [deployment_operations.md](deployment_operations.md) | Environments, environment variable names (xAI, Imagine, Gemini check, Backboard, and Ask included), Vultr provisioning, the clean-worktree deploy, Caddy and systemd hardening (with the image `CacheDirectory`), DNS and external services, Backboard setup and pruning, health checks, logs, rollback, cost, and a runbook. |
| [security_privacy.md](security_privacy.md) | Threat model, data minimization (Ask questions and memory included), input validation, signed Ask tokens, rate limiting and budgets, browser and systemd hardening, AI guardrails for explanations, Ask PathPro, and Grok Imagine with its Gemini check, secret handling and logging, the key-masking incident, scanning, fairness safeguards, and residual risks. |
| [testing_quality.md](testing_quality.md) | Test strategy, product-rule tests, measured suite counts and coverage, static analysis results, reviews, a latency sample, and known issues. |

## Diagrams

Each diagram's source is a Mermaid file in [diagrams/](diagrams/), copied as a Mermaid block into its document (rendered by GitHub) and rendered as a 2× PNG in [img/](img/):

| PNG | Diagram |
| --- | --- |
| [a1_context.png](img/a1_context.png) | System context (C4 level 1) |
| [a2_containers.png](img/a2_containers.png) | Containers (C4 level 2) |
| [a3_route_sequence.png](img/a3_route_sequence.png) | Plan-a-route sequence |
| [a4_explain_sequence.png](img/a4_explain_sequence.png) | "Why?" explanation chain (Grok first) |
| [a5_share_sequence.png](img/a5_share_sequence.png) | Share my walk |
| [a6_demo_flow.png](img/a6_demo_flow.png) | Offline demo transport |
| [a7_multimode.png](img/a7_multimode.png) | Walk and ride models in one bundle |
| [a8_safety_flow.png](img/a8_safety_flow.png) | Personal-safety data flow |
| [a9_imagine_sequence.png](img/a9_imagine_sequence.png) | Grok Imagine draws, Gemini checks, disk cache |
| [a10_ask_sequence.png](img/a10_ask_sequence.png) | Ask PathPro: server-built context, retrieval, validator, fallback |
| [a11_ask_memory.png](img/a11_ask_memory.png) | Ask PathPro opt-in memory: clone, Auto vs Readonly, Forget me |
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
| Tests (measured 2026-09-26) | data 237, API 655, web 640 passing; 19 Playwright end-to-end tests defined (1,551 in all) |
| Explanation chain | xAI Grok → Groq `gpt-oss-120b` → Gemini → Groq `gpt-oss-20b` → template, one validator |
| Paid-feature caps per day | Grok Imagine 40 (10 per client), Ask 300 (20 per client), memory clones 100 (3 per client) |

Related project documents: [model card](../model_card.md), [safety sources](../safety_sources.md), [process notes](../process/process_notes.md), [PRD](<../../Requirements (PRD).md>).

## Regenerating the diagrams and PDF

[render_pdf.py](render_pdf.py) keeps the three forms in step (run from the repository root; needs Node for mermaid-cli and Google Chrome):

```bash
# render one diagram's PNG (or: --diagrams all)
uv run --with markdown --with pillow python docs/technical/render_pdf.py --diagrams a9_imagine_sequence
# copy diagrams/*.mmd into the documents' Mermaid blocks
uv run --with markdown --with pillow python docs/technical/render_pdf.py --sync
# check the blocks match their sources, then print the PDF
uv run --with markdown --with pillow python docs/technical/render_pdf.py
```

PNGs are rendered with `npx -y @mermaid-js/mermaid-cli` (`--size 2000 -s 2 -b white`, font settings in [diagrams/mermaid.json](diagrams/mermaid.json)). The PDF is the seven documents converted to HTML with a print stylesheet, each Mermaid block replaced by its PNG and cross-document links turned into in-document links, printed by headless Chrome (`--print-to-pdf`). Images are downscaled to JPEG for print so the PDF stays under the repository's 5 MB pre-commit file limit; `img/` keeps the full-resolution PNGs.

The PNGs for A5–A8 and D1–D3 predate this script (Mermaid 11 in Playwright's Chromium); their sources in `diagrams/` are unchanged, so `--diagrams all` reproduces them in the current style.
