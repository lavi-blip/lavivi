"""Minimal Monday.com GraphQL client tailored to the Resources for Growing board."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from . import config
from .models import FitReport, Requirement, RfpAnalysis, Task


class MondayError(RuntimeError):
    pass


class MondayClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("MONDAY_API_KEY")
        if not self.api_key:
            raise MondayError("MONDAY_API_KEY is not set")

    def _request(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        response = requests.post(
            config.MONDAY_API_URL,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
                "API-Version": config.MONDAY_API_VERSION,
            },
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if "errors" in body:
            raise MondayError(json.dumps(body["errors"], ensure_ascii=False))
        return body["data"]

    def get_groups(self) -> list[dict]:
        data = self._request(
            "query ($board: [ID!]) { boards(ids: $board) { groups { id title } } }",
            {"board": [str(config.BOARD_ID)]},
        )
        return data["boards"][0]["groups"]

    def resolve_group_id(self, title: str) -> str:
        for group in self.get_groups():
            if group["title"].strip() == title.strip():
                return group["id"]
        raise MondayError(f"Group not found on board {config.BOARD_ID}: {title!r}")

    def create_item(
        self,
        *,
        group_id: str,
        item_name: str,
        column_values: dict[str, Any],
    ) -> str:
        _assert_no_forbidden(column_values)
        data = self._request(
            """
            mutation ($board: ID!, $group: String!, $name: String!, $vals: JSON!) {
              create_item(
                board_id: $board,
                group_id: $group,
                item_name: $name,
                column_values: $vals,
                create_labels_if_missing: true
              ) { id }
            }
            """,
            {
                "board": str(config.BOARD_ID),
                "group": group_id,
                "name": item_name,
                "vals": json.dumps(column_values, ensure_ascii=False),
            },
        )
        return data["create_item"]["id"]

    def create_subitem(
        self,
        *,
        parent_item_id: str,
        item_name: str,
        column_values: dict[str, Any],
    ) -> str:
        _assert_no_forbidden(column_values)
        data = self._request(
            """
            mutation ($parent: ID!, $name: String!, $vals: JSON!) {
              create_subitem(
                parent_item_id: $parent,
                item_name: $name,
                column_values: $vals,
                create_labels_if_missing: true
              ) { id }
            }
            """,
            {
                "parent": str(parent_item_id),
                "name": item_name,
                "vals": json.dumps(column_values, ensure_ascii=False),
            },
        )
        return data["create_subitem"]["id"]

    def create_update(self, *, item_id: str, body: str) -> str:
        data = self._request(
            """
            mutation ($item: ID!, $body: String!) {
              create_update(item_id: $item, body: $body) { id }
            }
            """,
            {"item": str(item_id), "body": body},
        )
        return data["create_update"]["id"]


def build_main_column_values(analysis: RfpAnalysis) -> dict[str, Any]:
    values: dict[str, Any] = {
        config.COL_REQUEST_TYPE: {"label": config.REQUEST_TYPE_VALUE},
        config.COL_OUR_STAGE: {"label": config.INITIAL_OUR_STAGE},
        config.COL_SOURCE: {"label": analysis.source_category},
        config.COL_DEADLINE: {"date": analysis.deadline.isoformat()},
        config.COL_SUBMISSION_ANALYSIS: {"text": analysis.submission_analysis_he},
    }
    if analysis.requested_amount_usd is not None:
        values[config.COL_BUDGET_REQUESTED] = str(analysis.requested_amount_usd)
    return values


def build_subitem_column_values(
    task: Task,
    deadline_date,
    *,
    executor: str | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        config.SUB_COL_TASK_TYPE: {"labels": [task.action_type]},
        config.SUB_COL_STATUS: {"label": config.DEFAULT_TASK_STATUS},
        config.SUB_COL_HOURS: str(task.estimated_hours),
        config.SUB_COL_DUE_DATE: {"date": task.due_date(deadline_date).isoformat()},
    }
    if executor:
        values[config.SUB_COL_EXECUTOR] = {"labels": [executor]}
    return values


def build_fit_report_column_values(report: FitReport) -> dict[str, Any]:
    """Main item column values from a deep FitReport."""
    analysis_text = (
        f"ציון התאמה: {report.fit_score}\n\n"
        f"{report.recommendation_he}\n\n"
        + (("סיבות להתאמה:\n" + "\n".join(f"• {r}" for r in report.fit_reasons) + "\n\n") if report.fit_reasons else "")
        + (("פסילות:\n" + "\n".join(f"• {d}" for d in report.disqualifiers)) if report.disqualifiers else "")
    ).strip()

    values: dict[str, Any] = {
        config.COL_REQUEST_TYPE: {"label": config.REQUEST_TYPE_VALUE},
        config.COL_OUR_STAGE: {"label": config.INITIAL_OUR_STAGE},
        config.COL_SOURCE: {"label": report.source_category},
        config.COL_DEADLINE: {"date": report.deadline.isoformat()},
        config.COL_SUBMISSION_ANALYSIS: {"text": analysis_text},
    }
    if report.requested_amount_usd is not None:
        values[config.COL_BUDGET_REQUESTED] = str(report.requested_amount_usd)
    return values


def build_requirement_column_values(
    req: Requirement,
    deadline_date,
    *,
    executor: str | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        config.SUB_COL_TASK_TYPE: {"labels": [req.action_type]},
        config.SUB_COL_STATUS: {"label": config.DEFAULT_TASK_STATUS},
        config.SUB_COL_HOURS: str(req.estimated_hours),
        config.SUB_COL_DUE_DATE: {"date": req.due_date(deadline_date).isoformat()},
    }
    if executor:
        values[config.SUB_COL_EXECUTOR] = {"labels": [executor]}
    return values


def _assert_no_forbidden(column_values: dict[str, Any]) -> None:
    overlap = set(column_values) & config.FORBIDDEN_COLUMNS
    if overlap:
        raise MondayError(
            "Refusing to write to forbidden columns: " + ", ".join(sorted(overlap))
        )
