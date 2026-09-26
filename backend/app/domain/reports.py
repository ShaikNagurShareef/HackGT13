"""Community street reports: fixed categories only (no free text, no PII, no abuse vector).

Reports are shown next to scores but never change a score or the LLM's evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, get_args

ReportCategory = Literal[
    "sidewalk_blocked",
    "signal_out",
    "construction",
    "poor_lighting",
    "flooding",
    "fast_traffic",
]

CATEGORY_LABELS: dict[str, str] = {
    "sidewalk_blocked": "Sidewalk blocked",
    "signal_out": "Crossing signal out",
    "construction": "Construction detour",
    "poor_lighting": "Poor street lighting",
    "flooding": "Flooding or standing water",
    "fast_traffic": "Fast-moving traffic",
}
assert set(CATEGORY_LABELS) == set(get_args(ReportCategory))

REPORT_TTL = timedelta(days=14)


@dataclass(frozen=True)
class StreetReport:
    seg_id: int
    category: str
    street: str
    lon: float
    lat: float
    confirmations: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    @property
    def label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)


@dataclass(frozen=True)
class CategoryCount:
    category: str
    reports: int
    confirmations: int

    @property
    def label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)
