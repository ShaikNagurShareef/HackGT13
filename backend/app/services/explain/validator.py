"""Reject LLM text that could mislead (GEN-02, EC-41, EC-42, PRD §7.4 copy rules)."""

from __future__ import annotations

import re

from app.services.explain.evidence import Evidence

MAX_SENTENCES = 3
MAX_CHARS = 420
BANNED = (
    "safe",
    "safest",
    "safer",
    "safety",
    "guarantee",
    "guaranteed",
    "crime",
    "criminal",
    "dangerous area",
    "dangerous neighborhood",
    "bad neighborhood",
    "bad area",
    "sketchy",
    "unsafe",
    "violent",
    "shooting",
    "robbery",
    "income",
    "race",
    "demographic",
)
_BANNED_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in BANNED) + r")\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w])")
_SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")
# Numbers that are clock-time words ("10 PM") are verified against the evidence time label.
_CLOCK_RE = re.compile(r"\b(\d{1,2})(?::\d{2})?\s*(AM|PM)\b", re.IGNORECASE)


def _evidence_strings(value: object, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _evidence_strings(v, out)
    elif isinstance(value, list | tuple):
        for v in value:
            _evidence_strings(v, out)


def _strip_evidence_strings(text: str, evidence: Evidence) -> str:
    """Street names ("10th Street", "I-85") and periods contain digits that are not claims."""
    strings: list[str] = []
    _evidence_strings(evidence.payload, strings)
    for s in sorted(strings, key=len, reverse=True):
        if len(s) > 2:
            text = re.sub(re.escape(s), " ", text, flags=re.IGNORECASE)
    return text


def sentence_count(text: str) -> int:
    return len([s for s in _SENTENCE_RE.split(text.strip()) if s.strip()])


def validation_errors(text: str, evidence: Evidence) -> list[str]:
    errors: list[str] = []
    stripped = text.strip()
    if not stripped:
        return ["empty"]
    if len(stripped) > MAX_CHARS:
        errors.append("too_long")
    if sentence_count(stripped) > MAX_SENTENCES:
        errors.append("too_many_sentences")
    if _BANNED_RE.search(stripped):
        errors.append("banned_phrase")
    without_clock = _CLOCK_RE.sub(" ", _strip_evidence_strings(stripped, evidence))
    time_label = str(evidence.payload.get("time", ""))
    for match in _CLOCK_RE.finditer(stripped):
        if f"{int(match.group(1))} {match.group(2).upper()}" != time_label:
            errors.append(f"unknown_time:{match.group(0)}")
    for raw in _NUMBER_RE.findall(without_clock):
        if round(float(raw), 1) not in evidence.numbers:
            errors.append(f"unknown_number:{raw}")
    return errors


def is_valid(text: str, evidence: Evidence) -> bool:
    return not validation_errors(text, evidence)
