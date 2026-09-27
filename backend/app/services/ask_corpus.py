"""The curated docs Ask PathPro answers from, and the numbers an answer may quote.

The same files are uploaded to Backboard by `app.tools.setup_backboard` and read here at
startup, so every number in an answer can be checked against the source text. A missing file
simply contributes nothing: with no corpus, any number in an answer is rejected (fail closed).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

log = logging.getLogger(__name__)

CORPUS_FILES: tuple[str, ...] = (
    "docs/model_card.md",
    "docs/metrics.json",
    "docs/safety_sources.md",
    "docs/decisions.md",
    "docs/technical/data_and_models.md",
    "docs/judge_qa.md",
)
# "1,250" or "74.3" or "2024"; digits glued to letters ("10th", "h3") are not claims.
NUMBER_RE = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])")
PERCENT_SCALE = 100.0


def parse_number(raw: str) -> float:
    """A quoted number, to one decimal place (how answers are compared)."""
    return round(float(raw.replace(",", "")), 1)


def _variants(raw: str) -> set[float]:
    """A corpus number as it may fairly be quoted: as is, rounded, or a fraction as a percent."""
    value = float(raw.replace(",", ""))
    out = {round(value, 1), float(round(value))}
    if 0 < value < 1:
        percent = value * PERCENT_SCALE
        out |= {round(percent, 1), float(round(percent))}
    return out


def allowed_numbers(texts: Iterable[str]) -> frozenset[float]:
    found: set[float] = set()
    for text in texts:
        for raw in NUMBER_RE.findall(text):
            found |= _variants(raw)
    return frozenset(found)


def corpus_paths(root: Path) -> tuple[Path, ...]:
    return tuple(root / name for name in CORPUS_FILES if (root / name).is_file())


def load_allowed_numbers(root: Path) -> frozenset[float]:
    """Numbers from the corpus files under the repo root; empty (fail closed) if none exist."""
    texts: list[str] = []
    for path in corpus_paths(root):
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("ask corpus file unreadable: %s", type(exc).__name__)
    return allowed_numbers(texts)
