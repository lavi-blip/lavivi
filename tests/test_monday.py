"""Tests for the Monday.com client with HTTP mocked."""

from __future__ import annotations

from datetime import date

import pytest

from src import config
from src.models import RfpAnalysis, Task
from src.monday import (
    MondayClient,
    MondayError,
    build_main_column_values,
    build_subitem_column_values,
)


def _analysis() -> RfpAnalysis:
    return RfpAnalysis(
        title_he="קול קורא בדיקה",
        funder="קרן בדיקה",
        deadline=date(2026, 8, 15),
        origin="israel",
        source_category="קרנות פילנתרופיות",
        submission_analysis_he="ניתוח לדוגמה. שלוש שורות. בודקים.",
        requested_amount_usd=50000,
        tasks=[
            Task(
                name_he="יצירת קשר",
                action_type="יצירת קשר",
                estimated_hours=2,
                days_before_deadline=30,
            ),
            Task(
                name_he="הגשה",
                action_type="הגשה",
                estimated_hours=10,
                days_before_deadline=3,
            ),
        ],
    )


def test_main_column_values_include_all_required_guards():
    values = build_main_column_values(_analysis())
    assert values[config.COL_REQUEST_TYPE] == {"label": config.REQUEST_TYPE_VALUE}
    assert values[config.COL_OUR_STAGE] == {"label": config.INITIAL_OUR_STAGE}
    assert values[config.COL_DEADLINE] == {"date": "2026-08-15"}
    assert values[config.COL_SUBMISSION_ANALYSIS]["text"]
    for forbidden in config.FORBIDDEN_COLUMNS:
        assert forbidden not in values


def test_subitem_values_include_hours_and_status():
    task = _analysis().tasks[0]
    values = build_subitem_column_values(task, date(2026, 8, 15))
    assert values[config.SUB_COL_HOURS] == "2"
    assert values[config.SUB_COL_STATUS] == {"label": config.DEFAULT_TASK_STATUS}
    assert values[config.SUB_COL_DUE_DATE] == {"date": "2026-07-16"}
    assert values[config.SUB_COL_TASK_TYPE] == {"labels": ["יצירת קשר"]}
    for forbidden in config.FORBIDDEN_COLUMNS:
        assert forbidden not in values


def test_subitem_executor_uses_dropdown_only():
    task = _analysis().tasks[0]
    values = build_subitem_column_values(task, date(2026, 8, 15), executor="לביא")
    assert values[config.SUB_COL_EXECUTOR] == {"labels": ["לביא"]}
    assert "color_mkxrf6kb" not in values


def test_client_rejects_writes_to_forbidden_columns(monkeypatch):
    monkeypatch.setenv("MONDAY_API_KEY", "fake")
    client = MondayClient()
    with pytest.raises(MondayError, match="forbidden"):
        client.create_item(
            group_id="g",
            item_name="x",
            column_values={"color_mkxrf6kb": {"label": "x"}},
        )
    with pytest.raises(MondayError, match="forbidden"):
        client.create_subitem(
            parent_item_id="1",
            item_name="x",
            column_values={"color_mkxra7wc": {"label": "x"}},
        )


def test_task_rejects_zero_hours():
    with pytest.raises(ValueError, match="estimated_hours"):
        Task(
            name_he="bad",
            action_type="הגשה",
            estimated_hours=0,
            days_before_deadline=5,
        )
