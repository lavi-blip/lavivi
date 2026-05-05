"""Tests for the deep-analysis path (fit_checker + new Monday helpers)."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from src.fit_checker import _extract_json, _to_report
from src.models import FitReport, Requirement
from src.monday import (
    MondayError,
    build_fit_report_column_values,
    build_requirement_column_values,
)
from src import config


def _fit_payload(**overrides) -> dict:
    base = {
        "title_he": "קרן לדוגמה",
        "funder": "קרן בדיקה",
        "deadline": "2026-10-01",
        "requested_amount_usd": 60000,
        "origin": "israel",
        "source_category": "קרנות פילנתרופיות",
        "fit_score": "גבוה",
        "fit_reasons": ["פעילות קהילתית מתאימה"],
        "disqualifiers": [],
        "recommendation_he": "מומלץ להגיש.",
        "requirements": [
            {
                "name_he": "כתיבת תקציר מנהלים",
                "action_type": "הכנת תוכן",
                "estimated_hours": 4,
                "days_before_deadline": 14,
                "is_autonomous": True,
                "prepared_content": "תקציר: צומחים מחדש פועלת...",
                "human_instructions": None,
            },
            {
                "name_he": "חתימת עו\"ד",
                "action_type": "אדמניסטרציה",
                "estimated_hours": 1,
                "days_before_deadline": 21,
                "is_autonomous": False,
                "prepared_content": None,
                "human_instructions": "פנה לעו\"ד X לחתימה על תצהיר.",
            },
        ],
        "questions": [
            {
                "question_he": "תאר את מטרות הפרויקט",
                "draft_answer_he": "צומחים מחדש פועלת למען...",
            }
        ],
    }
    base.update(overrides)
    return base


def test_to_report_happy_path():
    report = _to_report(_fit_payload())
    assert isinstance(report, FitReport)
    assert report.fit_score == "גבוה"
    assert report.deadline == date(2026, 10, 1)
    assert len(report.requirements) == 2
    assert len(report.questions) == 1
    assert report.is_worth_submitting


def test_to_report_blocks_missing_deadline():
    with pytest.raises(ValueError, match="מועד הגשה"):
        _to_report(_fit_payload(deadline=None))


def test_to_report_disqualifiers_block_submission():
    report = _to_report(_fit_payload(disqualifiers=["לא עומדים בתנאי הסף"]))
    assert not report.is_worth_submitting


def test_to_report_unknown_fit_score_defaults():
    report = _to_report(_fit_payload(fit_score="מה זה בכלל"))
    assert report.fit_score == "נמוך"


def test_fit_report_column_values_no_forbidden():
    from src.models import ApplicationQuestion
    report = _to_report(_fit_payload())
    values = build_fit_report_column_values(report)
    assert values[config.COL_REQUEST_TYPE] == {"label": config.REQUEST_TYPE_VALUE}
    assert values[config.COL_OUR_STAGE] == {"label": config.INITIAL_OUR_STAGE}
    assert config.COL_DEADLINE in values
    assert config.COL_SUBMISSION_ANALYSIS in values
    for forbidden in config.FORBIDDEN_COLUMNS:
        assert forbidden not in values


def test_requirement_column_values_hours_always_filled():
    req = Requirement(
        name_he="בדיקת תנאי סף",
        action_type="בדיקת התאמה",
        estimated_hours=2.5,
        days_before_deadline=10,
        is_autonomous=True,
    )
    values = build_requirement_column_values(req, date(2026, 10, 1))
    assert values[config.SUB_COL_HOURS] == "2.5"
    assert values[config.SUB_COL_STATUS] == {"label": config.DEFAULT_TASK_STATUS}
    assert values[config.SUB_COL_DUE_DATE] == {"date": "2026-09-21"}
    for forbidden in config.FORBIDDEN_COLUMNS:
        assert forbidden not in values


def test_create_update_added_to_client(monkeypatch):
    monkeypatch.setenv("MONDAY_API_KEY", "fake")
    from src.monday import MondayClient
    client = MondayClient()
    # Patch _request to capture calls
    calls = []
    monkeypatch.setattr(client, "_request", lambda q, v=None: calls.append((q, v)) or {"create_update": {"id": "1"}})
    result = client.create_update(item_id="123", body="hello")
    assert result == "1"
    assert any("create_update" in q for q, _ in calls)
