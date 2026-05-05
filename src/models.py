"""Structured data extracted from a call-for-proposals page."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


Origin = Literal["israel", "abroad"]
FitScore = Literal["גבוה", "בינוני", "נמוך", "לא מתאים"]


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
        if self.days_before_deadline < -30:
            raise ValueError(
                f"Task {self.name_he!r} is scheduled more than 30 days after the deadline."
            )

    def due_date(self, deadline: date) -> date:
        from datetime import timedelta
        return deadline - timedelta(days=self.days_before_deadline)


@dataclass
class RfpAnalysis:
    title_he: str
    funder: str
    deadline: date | None
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


@dataclass
class Requirement:
    name_he: str
    action_type: str
    estimated_hours: float
    days_before_deadline: int
    is_autonomous: bool
    prepared_content: str | None = None
    human_instructions: str | None = None

    def __post_init__(self) -> None:
        if self.estimated_hours <= 0:
            raise ValueError(
                f"Requirement {self.name_he!r} must have estimated_hours > 0"
            )

    def due_date(self, deadline: date) -> date:
        from datetime import timedelta
        return deadline - timedelta(days=self.days_before_deadline)


@dataclass
class ApplicationQuestion:
    question_he: str
    draft_answer_he: str


@dataclass
class FitReport:
    title_he: str
    funder: str
    deadline: date | None
    origin: Origin
    source_category: str
    fit_score: FitScore
    fit_reasons: list[str]
    disqualifiers: list[str]
    recommendation_he: str
    requirements: list[Requirement] = field(default_factory=list)
    questions: list[ApplicationQuestion] = field(default_factory=list)
    requested_amount_usd: float | None = None

    @property
    def is_worth_submitting(self) -> bool:
        return self.fit_score in ("גבוה", "בינוני") and not self.disqualifiers
