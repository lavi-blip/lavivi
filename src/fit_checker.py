"""Deep fit analysis using any supported LLM provider (Claude or Gemini)."""

from __future__ import annotations

import json
from datetime import date

from .config import SOURCE_CATEGORIES, TASK_TYPES
from .llm import LLMClient, Provider, from_env
from .models import ApplicationQuestion, FitReport, FitScore, Requirement


SYSTEM_PROMPT = """אתה יועץ אסטרטגי בכיר לגיוס משאבים.
תפקידך לנתח קול קורא מול פרופיל הארגון שלהלן ולהחליט:
א) האם הארגון מתאים להגיש?
ב) מה בדיוק נדרש — מה אפשר להכין אוטומטית ומה דורש מגע אנושי?
ג) לכל משימה אוטומטית — לכתוב את התוכן המלא.

פרופיל הארגון:
{profile}

עקרונות:
- בדוק כל תנאי סף בקפידה (גיאוגרפיה, גודל, נושא, סוג עמותה).
- היה קונקרטי: "נדרש עו\"ד" ולא "עלולים לדרוש".
- עבור תשובות לשאלות — כתוב טיוטה מלאה, לא סכמה.
- אל תמציא נתונים שאינם בפרופיל הארגון.
- החזר JSON תקני בלבד, ללא הסברים נוספים."""


def _user_prompt(content: str) -> str:
    task_types_list = "\n".join(f"- {t}" for t in TASK_TYPES)
    categories_list = "\n".join(f"- {c}" for c in SOURCE_CATEGORIES)
    return f"""נתח את קול הקורא הבא והחזר JSON:

{{
  "title_he": "שם הקול הקורא",
  "funder": "שם הגוף המפרסם",
  "deadline": "YYYY-MM-DD או null",
  "requested_amount_usd": מספר או null,
  "origin": "israel" | "abroad",
  "source_category": "אחת מהקטגוריות",
  "fit_score": "גבוה" | "בינוני" | "נמוך" | "לא מתאים",
  "fit_reasons": ["סיבה 1", "סיבה 2"],
  "disqualifiers": ["פסילה 1"],
  "recommendation_he": "המלצה מנומקת בעברית",
  "requirements": [
    {{
      "name_he": "שם המשימה",
      "action_type": "אחד מסוגי הפעולה",
      "estimated_hours": מספר חיובי,
      "days_before_deadline": מספר שלם אי-שלילי,
      "is_autonomous": true | false,
      "prepared_content": "תוכן מוכן (אם is_autonomous=true) או null",
      "human_instructions": "הנחיות למשתמש (אם is_autonomous=false) או null"
    }}
  ],
  "questions": [
    {{
      "question_he": "שאלה מהבקשה",
      "draft_answer_he": "טיוטת תשובה מלאה בעברית"
    }}
  ]
}}

קטגוריות מקור:
{categories_list}

סוגי פעולה (action_type):
{task_types_list}

תוכן הקול הקורא:
---
{content}
---"""


def check_fit(
    content: str,
    org_profile: str,
    *,
    llm: LLMClient | None = None,
    provider: Provider = "claude",
) -> FitReport:
    if not content.strip():
        raise ValueError("Cannot analyze empty content")

    llm = llm or from_env()
    system = SYSTEM_PROMPT.format(profile=org_profile)
    raw = llm.complete(system=system, user=_user_prompt(content), max_tokens=8192)
    payload = _extract_json(raw)
    return _to_report(payload)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _to_report(p: dict) -> FitReport:
    deadline_raw = p.get("deadline")
    if not deadline_raw:
        raise ValueError(
            "לא נמצא מועד הגשה בקול הקורא. אי אפשר ליצור פריט ב-Monday ללא תאריך יעד."
        )

    source_category = p.get("source_category", "")
    if source_category not in SOURCE_CATEGORIES:
        source_category = "כללי"

    requirements = [
        Requirement(
            name_he=r["name_he"],
            action_type=r.get("action_type", "אדמניסטרציה"),
            estimated_hours=max(float(r["estimated_hours"]), 0.5),
            days_before_deadline=int(r["days_before_deadline"]),
            is_autonomous=bool(r.get("is_autonomous", False)),
            prepared_content=r.get("prepared_content"),
            human_instructions=r.get("human_instructions"),
        )
        for r in p.get("requirements", [])
    ]

    questions = [
        ApplicationQuestion(
            question_he=q["question_he"],
            draft_answer_he=q["draft_answer_he"],
        )
        for q in p.get("questions", [])
    ]

    amount = p.get("requested_amount_usd")
    return FitReport(
        title_he=p["title_he"].strip(),
        funder=p.get("funder", "").strip(),
        deadline=date.fromisoformat(deadline_raw),
        origin=p.get("origin", "israel"),
        source_category=source_category,
        fit_score=_normalize_score(p.get("fit_score", "נמוך")),
        fit_reasons=p.get("fit_reasons", []),
        disqualifiers=p.get("disqualifiers", []),
        recommendation_he=p.get("recommendation_he", "").strip(),
        requirements=requirements,
        questions=questions,
        requested_amount_usd=float(amount) if amount is not None else None,
    )


def _normalize_score(value: str) -> FitScore:
    valid: tuple[FitScore, ...] = ("גבוה", "בינוני", "נמוך", "לא מתאים")
    return value if value in valid else "נמוך"
