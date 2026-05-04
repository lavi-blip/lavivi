"""Claude-powered extraction of structured RFP data."""

from __future__ import annotations

import json
import os
from datetime import date

from anthropic import Anthropic

from .config import CLAUDE_MODEL, SOURCE_CATEGORIES, TASK_TYPES
from .models import RfpAnalysis, Task


SYSTEM_PROMPT = """אתה מומחה לניתוח קולות קוראים (RFPs) עבור צוות גיוס משאבים בעמותה.
תפקידך לחלץ מידע מובנה מטקסט של קול קורא, ולהציע רשימת משימות שיש לבצע
על מנת להגיש בקשה.

הקפד:
- לזהות במדויק את מועד ההגשה האחרון. אם אין תאריך ברור — החזר deadline=null.
- לסווג את המקור לאחת מקטגוריות מקור הקיימות בלבד.
- לייצר רשימת משימות בסדר העבודה המקובל:
  יצירת קשר → פגישה (אם רלוונטי) → הכנת תוכן → הגשה → פולואפ.
- לכל משימה — להעריך שעות עבודה ריאליות (לעולם לא 0).
- לכל משימה — לקבוע מספר ימים לפני הדדליין שבהם יש להשלים אותה.
- לכתוב את ה-Submission Analysis בעברית, בלפחות 3 משפטים, עם הערכת
  התאמה / סיכויי הצלחה / מורכבות.

החזר JSON תקני בלבד, ללא הסברים נוספים."""


def _user_prompt(content: str) -> str:
    categories_list = "\n".join(f"- {c}" for c in SOURCE_CATEGORIES)
    task_types_list = "\n".join(f"- {t}" for t in TASK_TYPES)
    return f"""נתח את תוכן הקול הקורא הבא והחזר JSON במבנה הבא:

{{
  "title_he": "שם הקול הקורא בעברית",
  "funder": "שם הגוף המפרסם",
  "deadline": "YYYY-MM-DD או null אם אין תאריך ברור",
  "requested_amount_usd": מספר או null,
  "origin": "israel" או "abroad",
  "source_category": "אחת מהקטגוריות הבאות בלבד",
  "submission_analysis_he": "ניתוח בעברית, לפחות 3 משפטים",
  "tasks": [
    {{
      "name_he": "שם המשימה",
      "action_type": "אחד מסוגי הפעולה הבאים בלבד",
      "estimated_hours": מספר חיובי,
      "days_before_deadline": מספר שלם אי-שלילי
    }}
  ]
}}

קטגוריות מקור אפשריות:
{categories_list}

סוגי פעולה אפשריים (action_type):
{task_types_list}

תוכן הקול הקורא:
---
{content}
---"""


def analyze_rfp(content: str, *, client: Anthropic | None = None) -> RfpAnalysis:
    if not content.strip():
        raise ValueError("Cannot analyze empty content")

    client = client or Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(content)}],
    )

    raw = "".join(block.text for block in message.content if block.type == "text")
    payload = _extract_json(raw)
    return _to_analysis(payload)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _to_analysis(payload: dict) -> RfpAnalysis:
    deadline_raw = payload.get("deadline")
    if not deadline_raw:
        raise ValueError(
            "Claude could not extract a deadline from the RFP content. "
            "Refusing to create a Monday item without one — please supply the "
            "deadline manually or use a clearer source."
        )

    source_category = payload.get("source_category", "")
    if source_category not in SOURCE_CATEGORIES:
        source_category = "כללי"

    tasks = [
        Task(
            name_he=t["name_he"],
            action_type=_normalize_task_type(t["action_type"]),
            estimated_hours=float(t["estimated_hours"]),
            days_before_deadline=int(t["days_before_deadline"]),
        )
        for t in payload.get("tasks", [])
    ]

    amount = payload.get("requested_amount_usd")
    return RfpAnalysis(
        title_he=payload["title_he"].strip(),
        funder=payload.get("funder", "").strip(),
        deadline=date.fromisoformat(deadline_raw),
        origin=payload["origin"],
        source_category=source_category,
        submission_analysis_he=payload["submission_analysis_he"].strip(),
        requested_amount_usd=float(amount) if amount is not None else None,
        tasks=tasks,
    )


def _normalize_task_type(value: str) -> str:
    if value in TASK_TYPES:
        return value
    return "אדמניסטרציה"
