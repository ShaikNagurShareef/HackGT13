"""Reject LLM text that could mislead (GEN-02, EC-41, EC-42, PRD §7.4 copy rules)."""

from __future__ import annotations

import re

from app.services.ask_corpus import NUMBER_RE, parse_number
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


# --- Ask PathPro (Backboard) answers ----------------------------------------------------------
# Answers about PathPro itself may name crime data to say how it is (not) used, and may name the
# personal-safety layer; every other explanation rule still applies, plus crime-framing checks.
ASK_MAX_WORDS = 140  # the assistant is told 120; a little slack for formatting
ASK_MAX_CHARS = 1000
ASK_ALLOWED = frozenset({"crime", "safety"})
ASK_EXTRA_BANNED = ("dangerous", "high-risk neighborhood", "crime-ridden", "ghetto")
ASK_BANNED = tuple(b for b in BANNED if b not in ASK_ALLOWED) + ASK_EXTRA_BANNED
_ASK_BANNED_RE = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in ASK_BANNED) + r")\b", re.IGNORECASE
)
_CRIME_FRAMING_RE = re.compile(
    r"\bhigh[- ]crime\b"
    r"|\bcrime[- ]?(?:ridden|infested|hot ?spots?|zones?|areas?|neighbou?rhoods?)\b"
    r"|\b(?:rough|sketchy|bad|shady)\s+(?:areas?|neighbou?rhoods?|parts? of town|side of town)\b"
    r"|\bavoid(?:s|ing)?\s+(?:the\s+|this\s+|that\s+|these\s+|those\s+)?"
    r"(?:areas?|neighbou?rhoods?)\b",
    re.IGNORECASE,
)
_CRIME_RE = re.compile(r"\bcrim(?:e|es|inal)\b", re.IGNORECASE)
# Crime may be mentioned next to routing or scoring only to say it is NOT used there.
_ROUTING_OR_SCORE_RE = re.compile(r"\b(?:rout\w*|scor\w*|cost\w*|model\w*)\b", re.IGNORECASE)
_NEGATION_RE = re.compile(
    r"\b(?:never|not|no|without|excluded?|informational)\b|n't\b", re.IGNORECASE
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _crime_framing(text: str) -> bool:
    if _CRIME_FRAMING_RE.search(text):
        return True
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if (
            _CRIME_RE.search(sentence)
            and _ROUTING_OR_SCORE_RE.search(sentence)
            and not _NEGATION_RE.search(sentence)
        ):
            return True
    return False


def ask_validation_errors(text: str, allowed: frozenset[float]) -> list[str]:
    """Why an Ask PathPro answer may not be shown; every number must come from the corpus."""
    stripped = text.strip()
    if not stripped:
        return ["empty"]
    errors: list[str] = []
    if len(stripped) > ASK_MAX_CHARS or len(stripped.split()) > ASK_MAX_WORDS:
        errors.append("too_long")
    if _ASK_BANNED_RE.search(stripped):
        errors.append("banned_phrase")
    if _crime_framing(stripped):
        errors.append("crime_framing")
    for raw in NUMBER_RE.findall(stripped):
        value = parse_number(raw)
        if value not in allowed:
            errors.append(f"unknown_number:{int(value) if value.is_integer() else value}")
    return errors
