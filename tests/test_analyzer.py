"""Tests for the Claude analyzer with the API call mocked."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from src.analyzer import _extract_json, _to_analysis, analyze_rfp
from src.models import RfpAnalysis


def _payload(**overrides) -> dict:
    base = {
        "title_he": "קול קורא לדוגמה",
        "funder": "קרן הדוגמה",
        "deadline": "2026-08-15",
        "requested_amount_usd": 50000,
        "origin": "israel",
        "source_category": "קרנות פילנתרופיות",
        "submission_analysis_he": "התאמה גבוהה. נדרש מאמץ בינוני. סיכוי הצלחה סביר.",
        "tasks": [
            {
                "name_he": "יצירת קשר ראשונית",
                "action_type": "יצירת קשר",
                "estimated_hours": 1.5,
                "days_before_deadline": 30,
            },
            {
                "name_he": "הכנת מסמכי הגשה",
                "action_type": "הכנת תוכן",
                "estimated_hours": 8,
                "days_before_deadline": 7,
            },
        ],
    }
    base.update(overrides)
    return base


class FakeMessage:
    def __init__(self, payload: dict) -> None:
        self.content = [SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))]


class FakeAnthropic:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **_kwargs) -> FakeMessage:
        return FakeMessage(self.payload)


def test_analyze_rfp_happy_path():
    client = FakeAnthropic(_payload())
    result = analyze_rfp("some content", client=client)
    assert isinstance(result, RfpAnalysis)
    assert result.deadline == date(2026, 8, 15)
    assert result.origin == "israel"
    assert len(result.tasks) == 2
    assert all(t.estimated_hours > 0 for t in result.tasks)


def test_analyze_rfp_returns_none_deadline_when_missing():
    client = FakeAnthropic(_payload(deadline=None))
    result = analyze_rfp("some content", client=client)
    assert result.deadline is None


def test_analyze_rfp_rejects_zero_hours():
    payload = _payload()
    payload["tasks"][0]["estimated_hours"] = 0
    client = FakeAnthropic(payload)
    with pytest.raises(ValueError, match="estimated_hours"):
        analyze_rfp("some content", client=client)


def test_analyze_rfp_rejects_empty_content():
    with pytest.raises(ValueError, match="empty"):
        analyze_rfp("   ", client=FakeAnthropic(_payload()))


def test_unknown_source_category_falls_back_to_general():
    analysis = _to_analysis(_payload(source_category="קטגוריה שלא קיימת"))
    assert analysis.source_category == "כללי"


def test_unknown_action_type_falls_back():
    payload = _payload()
    payload["tasks"][0]["action_type"] = "פעולה מומצאת"
    analysis = _to_analysis(payload)
    assert analysis.tasks[0].action_type == "אדמניסטרציה"


def test_extract_json_strips_code_fences():
    raw = "```json\n" + json.dumps({"a": 1}) + "\n```"
    assert _extract_json(raw) == {"a": 1}
