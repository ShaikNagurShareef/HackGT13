"""Reject LLM text that could mislead (GEN-02, EC-41, EC-42, PRD §7.4 copy rules)."""

from __future__ import annotations

import re

from app.services.ask_corpus import NUMBER_RE, allowed_numbers, parse_number
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
_BANNED_RE = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in BANNED) + r")(?:e?s)?\b", re.IGNORECASE
)
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
# "income" and "demographic" may appear only to say PathPro does not use them.
ASK_NEGATABLE = frozenset({"income", "demographic"})
ASK_BANNED = tuple(b for b in BANNED if b not in ASK_ALLOWED | ASK_NEGATABLE) + ASK_EXTRA_BANNED
_ASK_NEGATABLE_RE = re.compile(r"\b(" + "|".join(sorted(ASK_NEGATABLE)) + r")s?\b", re.IGNORECASE)
_ASK_BANNED_RE = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in ASK_BANNED) + r")(?:e?s)?\b", re.IGNORECASE
)
# Code identifiers such as lit_and_busy are internal names, never user-facing words.
_INTERNAL_TERM_RE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
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
    r"\b(?:never|not|no|without|exclude[sd]?|informational|separate(?:d|ly)?|independent(?:ly)?"
    r"|rather\s+than|instead\s+of)\b|n't\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _unnegated_demographics(text: str) -> bool:
    """Naming income or demographics is fine only in a sentence saying they are not used."""
    return any(
        _ASK_NEGATABLE_RE.search(sentence) and not _NEGATION_RE.search(sentence)
        for sentence in _SENTENCE_SPLIT_RE.split(text)
    )


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


# Answers carry no links, domains or email addresses (a prompt-injected docs page or a model
# slip could otherwise point people elsewhere); only PathPro's own domain may be named.
# The allowed domain may end a sentence ("pathpro.tech.") but not prefix another host.
_ALLOWED_DOMAIN_RE = re.compile(
    r"(?<![\w.@/-])(?:https?://)?(?:www\.)?pathpro\.tech\b/?(?![\w@-]|\.\w)", re.IGNORECASE
)
_LINK_RE = re.compile(
    r"https?://|\bwww\.|@|\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)*\.[a-z]{2,24}\b",
    re.IGNORECASE,
)
# The answer must be about PathPro: at least one of its terms (word start, any case).
ASK_TOPIC_TERMS = (
    "PathPro",
    "traffic risk",
    "route",
    "crash",
    "model",
    "street",
    "walk",
    "ride",
    "MARTA",
    "High Injury Network",
    "score",
    "lighting",
    "help point",
    "Risk Tides",
    "City Pulse",
    "Share my walk",
)
_TOPIC_RE = re.compile(
    r"\b(?:"
    + "|".join(r"[\s-]+".join(re.escape(w) for w in t.split()) for t in ASK_TOPIC_TERMS)
    + r")",
    re.IGNORECASE,
)


# Answers may cite the corpus files they were drawn from ("metrics.json" is not a domain).
CORPUS_FILE_NAMES = (
    "model_card.md",
    "metrics.json",
    "safety_sources.md",
    "decisions.md",
    "data_and_models.md",
    "judge_qa.md",
    "user_guide.md",
    "README.md",
)
CORPUS_FILE_RE = re.compile(
    r"(?<![\w.@-])(?:[\w-]+/)*(?:"
    + "|".join(re.escape(n) for n in CORPUS_FILE_NAMES)
    + r")(?![\w@-]|\.\w)",
    re.IGNORECASE,
)


def ask_banned_words(text: str) -> tuple[str, ...]:
    """The banned words an Ask answer used (lower case, first-seen order), for a rewrite request."""
    found = [m.group(0).lower() for m in _ASK_BANNED_RE.finditer(text)]
    if _unnegated_demographics(text):
        found += [m.group(0).lower() for m in _ASK_NEGATABLE_RE.finditer(text)]
    return tuple(dict.fromkeys(found))


def internal_terms(text: str) -> tuple[str, ...]:
    """Code identifiers left in an Ask answer (corpus file names are not identifiers)."""
    return tuple(dict.fromkeys(_INTERNAL_TERM_RE.findall(CORPUS_FILE_RE.sub(" ", text))))


def _has_link(text: str) -> bool:
    cleaned = CORPUS_FILE_RE.sub(" ", _ALLOWED_DOMAIN_RE.sub(" ", text))
    return _LINK_RE.search(cleaned) is not None


def _on_topic(text: str) -> bool:
    return _TOPIC_RE.search(_ALLOWED_DOMAIN_RE.sub(" ", text)) is not None


def _ask_number_errors(
    text: str, allowed: frozenset[float], evidence: Evidence | None, question: str | None
) -> list[str]:
    """Numbers must come from the corpus, the context evidence, or the asker's own question.

    Evidence strings (street names such as "I-85") and clock times ("11 PM") are not claims.
    """
    permitted = allowed
    if evidence is not None:
        text = _strip_evidence_strings(text, evidence)
        permitted = permitted | evidence.numbers
    if question:
        permitted = permitted | allowed_numbers([question])
    errors: list[str] = []
    for raw in NUMBER_RE.findall(_CLOCK_RE.sub(" ", text)):
        value = parse_number(raw)
        if value not in permitted:
            errors.append(f"unknown_number:{int(value) if value.is_integer() else value}")
    return errors


def ask_validation_errors(
    text: str,
    allowed: frozenset[float],
    evidence: Evidence | None = None,
    question: str | None = None,
) -> list[str]:
    """Why an Ask PathPro answer may not be shown; every number must have a known source."""
    stripped = text.strip()
    if not stripped:
        return ["empty"]
    errors: list[str] = []
    if _has_link(stripped):
        errors.append("link")
    if not _on_topic(stripped):
        errors.append("off_topic")
    if len(stripped) > ASK_MAX_CHARS or len(stripped.split()) > ASK_MAX_WORDS:
        errors.append("too_long")
    if _ASK_BANNED_RE.search(stripped) or _unnegated_demographics(stripped):
        errors.append("banned_phrase")
    if _crime_framing(stripped):
        errors.append("crime_framing")
    if _INTERNAL_TERM_RE.search(CORPUS_FILE_RE.sub(" ", stripped)):
        errors.append("internal_term")
    return errors + _ask_number_errors(stripped, allowed, evidence, question)
