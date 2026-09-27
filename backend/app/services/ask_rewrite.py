"""Making an Ask PathPro answer showable: app labels for code identifiers, and rewrite requests.

`humanize_identifiers` runs on every upstream answer before validation, so a value the assistant
learned from the docs (lit_and_busy) reads as the label people see in the app (Well-lit &
busier). `repair_request` turns validator errors into the one follow-up message PathPro sends
when an answer is withheld; it names what to fix, never why a person asked.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.domain.reports import CATEGORY_LABELS
from app.services.explain.validator import CORPUS_FILE_RE, ask_banned_words, internal_terms

# Values the API and UI expose, as the app labels them.
IDENTIFIER_LABELS: dict[str, str] = {
    "lit_and_busy": "Well-lit & busier",
    "lower_traffic_risk": "lower traffic risk",
    "blue_light": "blue-light emergency phone",
    **{key: label[0].lower() + label[1:] for key, label in CATEGORY_LABELS.items()},
}
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z]+(?:_[A-Za-z0-9]+)+\b")
# Corpus file names (model_card.md) are matched first so they are kept as they are.
_FILE_OR_IDENTIFIER_RE = re.compile(
    f"(?P<file>{CORPUS_FILE_RE.pattern})|(?P<ident>{_IDENTIFIER_RE.pattern})", re.IGNORECASE
)
_INLINE_CODE_RE = re.compile(r"`([^`\n]*)`")

REPAIR_INTRO = (
    "Please rewrite your last answer so PathPro can show it. Keep the same facts, answer the "
    "same question, and fix these points:"
)
REPAIR_OUTRO = "Reply with the rewritten answer only."
_FIXED_INSTRUCTIONS: dict[str, str] = {
    "too_long": "Keep it to 120 words or fewer, in plain sentences.",
    "link": "Include no links, web addresses or email addresses, except pathpro.tech.",
    "off_topic": "Answer about PathPro: its traffic-risk map, routes, model, or features.",
    "crime_framing": (
        "Say that reported crimes against persons are informational only and are never used "
        "for routing or in traffic-risk scores; never describe any area by crime."
    ),
    "empty": "Give a short answer about PathPro.",
}
BANNED_INSTRUCTION = (
    "Do not use these words: {words}. Use 'lower-risk' or 'higher traffic risk' instead of "
    "safe/safer/safest/unsafe/dangerous, and describe traffic risk levels instead."
)
IDENTIFIER_INSTRUCTION = (
    "Do not use code identifiers ({terms}). Use the app's labels, e.g. 'Well-lit & busier' or "
    "'Lower traffic risk'."
)
NUMBER_INSTRUCTION = (
    "These numbers are not in PathPro's evidence: {numbers}. Use only numbers from the Context "
    "block or the documents, or leave the number out."
)


def _humanize(match: re.Match[str]) -> str:
    if match.group("file"):
        return match.group(0)
    word = match.group("ident")
    return IDENTIFIER_LABELS.get(word.lower(), word.replace("_", " "))


def humanize_identifiers(text: str) -> str:
    """App labels for known values; any other snake_case word loses its underscores."""
    return _FILE_OR_IDENTIFIER_RE.sub(_humanize, _INLINE_CODE_RE.sub(r"\1", text))


def error_kinds(errors: Sequence[str]) -> tuple[str, ...]:
    """Validator error categories ("unknown_number:97.5" -> "unknown_number"), sorted."""
    return tuple(sorted({e.split(":", 1)[0] for e in errors}))


def _instruction(kind: str, text: str, errors: Sequence[str]) -> str:
    if kind == "banned_phrase":
        words = ", ".join(ask_banned_words(text)) or "safe, safer, safest, unsafe, dangerous"
        return BANNED_INSTRUCTION.format(words=words)
    if kind == "internal_term":
        return IDENTIFIER_INSTRUCTION.format(terms=", ".join(internal_terms(text)) or "snake_case")
    if kind == "unknown_number":
        numbers = [e.split(":", 1)[1] for e in errors if e.startswith("unknown_number:")]
        return NUMBER_INSTRUCTION.format(numbers=", ".join(dict.fromkeys(numbers)))
    return _FIXED_INSTRUCTIONS.get(kind, "Follow the PathPro answer rules.")


def repair_request(text: str, errors: Sequence[str]) -> str:
    """The follow-up message asking the assistant to rewrite `text`: one line per error kind."""
    lines = [f"- {_instruction(kind, text, errors)}" for kind in error_kinds(errors)]
    return "\n".join([REPAIR_INTRO, *lines, REPAIR_OUTRO])
