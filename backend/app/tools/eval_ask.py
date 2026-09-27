"""Measure how often Ask PathPro gives a real (validated) answer instead of the fallback.

    uv run python -m app.tools.eval_ask                         # in-process app, real keys
    uv run python -m app.tools.eval_ask --base https://pathpro.tech/api --min-pass 0.9

Asks a fixed battery of everyday, how-to, prediction-explaining and tricky questions, with and
without on-screen context (a street, a route, a City Pulse area). Prints one line per question
and a summary; exits non-zero when the pass rate is below --min-pass. Never prints keys, and
never writes app data (no reports or shared walks; memory is never turned on).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

GENERAL = (
    "What is PathPro?",
    "How do I use PathPro?",
    "How do I start navigation?",
    "What does the risk score mean?",
    "What does 54% less traffic risk mean?",
    "How accurate is PathPro?",
    "How was the model tested?",
    "What data does PathPro use?",
    "What is Risk Tides?",
    "What is City Pulse?",
    "How do I share my walk with a friend?",
    "What are help points?",
    "How does the well-lit and busier option work?",
    "Can I use PathPro on a bike or scooter?",
    "When does PathPro suggest MARTA?",
    "Does PathPro work offline?",
    "Is my location stored?",
    "What does Imagine this street redesigned do?",
    "How does Ask PathPro remember my preferences?",
    "How is this different from Google Maps?",
    "Why does the route take longer?",
    "How does rain change traffic risk?",
    "Is it safe to walk on Peachtree Street at night?",
    "Which is the best route from Georgia Tech to Midtown?",
    "Who built PathPro?",
)
STREET = (
    "Why is this street high-risk at this hour?",
    "What would lower the risk here?",
    "Explain this prediction.",
    "How many crashes happened here?",
    "Is this street safe at night?",
)
ROUTE = (
    "Why is this route longer?",
    "Which stretches did it avoid?",
    "Explain this route's prediction.",
    "Is the fastest route much riskier?",
)
AREA = (
    "What drives traffic risk in this area?",
    "Explain this area's score.",
    "How does this area compare at night?",
)
KLAUS = {"lat": 33.7773, "lon": -84.3962}
MIDTOWN_MARTA = {"lat": 33.7810, "lon": -84.3864}
STREET_SEGMENTS = (0, 14278, 19399)
WHEN = "2026-09-25T22:30"


@dataclass(frozen=True)
class Case:
    question: str
    context: dict[str, Any] | None
    kind: str


@dataclass(frozen=True)
class Result:
    case: Case
    ok: bool
    detail: str


def build_cases(post: Callable[..., Any], get: Callable[..., Any]) -> list[Case]:
    cases = [Case(q, None, "general") for q in GENERAL]
    for i, q in enumerate(STREET):
        seg = STREET_SEGMENTS[i % len(STREET_SEGMENTS)]
        ctx = {"kind": "segment", "seg_id": seg, "t": WHEN, "cond": "wet", "mode": "walk"}
        cases.append(Case(q, ctx, "street"))
    route = post(
        "/routes",
        json={"origin": KLAUS, "destination": MIDTOWN_MARTA, "depart_at": WHEN, "cond": "wet"},
    )
    route_key = (route.json().get("data") or {}).get("route_key")
    if route_key:
        cases += [Case(q, {"kind": "route", "route_key": route_key}, "route") for q in ROUTE]
    area = get(
        "/areas/lookup", params={"lat": KLAUS["lat"], "lon": KLAUS["lon"], "t": WHEN, "cond": "wet"}
    )
    cell = (area.json().get("data") or {}).get("cell")
    if cell:
        ctx_area = {"kind": "area", "cell": cell, "t": WHEN, "cond": "wet"}
        cases += [Case(q, ctx_area, "area") for q in AREA]
    return cases


def run_case(post: Callable[..., Any], case: Case, pace_s: float = 0.0) -> Result:
    time.sleep(pace_s)  # stay under the per-minute paid-endpoint limit, like a person would
    body: dict[str, Any] = {"question": case.question}
    if case.context:
        body["context"] = case.context
    resp = post("/ask", json=body)
    data = resp.json().get("data") or {}
    if resp.status_code != 200:
        return Result(case, False, f"HTTP {resp.status_code}")
    if data.get("source") != "backboard":
        return Result(case, False, "fallback")
    if case.context and data.get("context_dropped"):
        return Result(case, False, "context dropped")
    if case.context and data.get("context_used") != case.context["kind"]:
        return Result(case, False, f"context_used={data.get('context_used')}")
    return Result(case, True, (data.get("answer") or "")[:110].replace("\n", " "))


def summarize(results: list[Result]) -> float:
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"{mark} [{r.case.kind:7s}] {r.case.question} -> {r.detail}")
    passed = sum(r.ok for r in results)
    rate = passed / len(results) if results else 0.0
    by_kind: dict[str, list[bool]] = {}
    for r in results:
        by_kind.setdefault(r.case.kind, []).append(r.ok)
    parts = ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in by_kind.items())
    print(f"\nanswered {passed}/{len(results)} ({rate:.0%}) · {parts}")
    return rate


def _run(post: Callable[..., Any], get: Callable[..., Any], pace_s: float) -> list[Result]:
    return [run_case(post, case, pace_s) for case in build_cases(post, get)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Ask PathPro's real-answer rate.")
    parser.add_argument("--base", help="API base URL (default: the app in-process)")
    parser.add_argument("--min-pass", type=float, default=0.9)
    parser.add_argument("--pace", type=float, default=2.5, help="seconds between questions")
    args = parser.parse_args(argv)
    if args.base:
        with httpx.Client(base_url=args.base.rstrip("/"), timeout=90) as client:
            results = _run(client.post, client.get, args.pace)
    else:
        from fastapi.testclient import TestClient

        from app.config import Settings
        from app.main import create_app

        with TestClient(create_app(Settings())) as tc:
            results = _run(tc.post, tc.get, 0.0)
    return 0 if summarize(results) >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
