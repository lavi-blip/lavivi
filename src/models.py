"""Structured data extracted from a call-for-proposals page."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


Origin = Literal["israel", "abroad"]


@dataclass
class Task:
    name_he: str
    action_type: str
    estimated_hours: float
    days_before_deadline: int

    def __post_init__(self) -> None:
        if self.estimated_hours <= 0:
            raise ValueError(
                f"Task {self.name_he!r} must have estimated_hours > 0 "
                "(otherwise the DONE*כמות שעות formula in Monday will error)."
            )
        if self.days_before_deadline < 0:
            raise ValueError(
                f"Task {self.name_he!r} cannot be scheduled after the deadline."
            )

    def due_date(self, deadline: date) -> date:
        from datetime import timedelta
        return deadline - timedelta(days=self.days_before_deadline)


@dataclass
class RfpAnalysis:
    title_he: str
    funder: str
    deadline: date
    origin: Origin
    source_category: str
    submission_analysis_he: str
    requested_amount_usd: float | None = None
    tasks: list[Task] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.title_he.strip():
            raise ValueError("title_he is required")
        if not self.submission_analysis_he.strip():
            raise ValueError("submission_analysis_he is required")
        if self.origin not in ("israel", "abroad"):
            raise ValueError(f"origin must be 'israel' or 'abroad', got {self.origin!r}")
        if not self.tasks:
            raise ValueError("at least one task is required")
