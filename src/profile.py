"""Load org profile and enrich it with learnings from past Monday submissions."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from . import config

PROFILE_PATH = Path(__file__).parent.parent / "org_profile.md"
LEARNED_SECTION_MARKER = "## למידה מהגשות קודמות (מוזן אוטומטית)"
MAX_HISTORY_ITEMS = 30


def load(*, include_monday_history: bool = True) -> str:
    """Return combined org profile text for use in Claude prompts."""
    base = _load_file()
    if not include_monday_history:
        return base
    try:
        from .monday import MondayClient
        history = _extract_history(MondayClient())
    except Exception:
        history = ""
    if history:
        return _inject_history(base, history)
    return base


def _load_file() -> str:
    if PROFILE_PATH.exists():
        return PROFILE_PATH.read_text(encoding="utf-8")
    return "(פרופיל ארגון לא נמצא — הרץ --build-profile או מלא את org_profile.md)"


def _inject_history(base: str, history: str) -> str:
    if LEARNED_SECTION_MARKER in base:
        idx = base.index(LEARNED_SECTION_MARKER) + len(LEARNED_SECTION_MARKER)
        return base[:idx] + "\n\n" + history + base[idx:]
    return base + "\n\n" + LEARNED_SECTION_MARKER + "\n\n" + history


def _extract_history(client) -> str:
    """Pull approved + declined items from the board and summarise learnings."""
    query = """
    query ($board: [ID!]) {
      boards(ids: $board) {
        items_page(limit: 50) {
          items {
            name
            column_values(ids: [
              "color_mkphtbwm", "color0", "status__1",
              "numeric", "numeric_mm2wvg5y",
              "long_text_mkqgjve6"
            ]) { id text value }
          }
        }
      }
    }
    """
    try:
        data = client._request(query, {"board": [str(config.BOARD_ID)]})
        items = data["boards"][0]["items_page"]["items"]
    except Exception:
        return ""

    approved, declined = [], []
    for item in items:
        cols = {c["id"]: c["text"] for c in item["column_values"]}
        their_stage = cols.get("status__1", "")
        analysis = cols.get("long_text_mkqgjve6", "")
        amount_received = cols.get("numeric_mm2wvg5y", "")
        if "approv" in their_stage.lower() or "אושר" in their_stage:
            approved.append((item["name"], amount_received, analysis))
        elif "declin" in their_stage.lower() or "נדח" in their_stage:
            declined.append((item["name"], analysis))

    lines: list[str] = []
    if approved:
        lines.append("### הגשות שאושרו (ניסיון מוצלח)")
        for name, amount, analysis in approved[:MAX_HISTORY_ITEMS // 2]:
            amt_str = f" | סכום: ₪/$ {amount}" if amount else ""
            lines.append(f"- **{name}**{amt_str}")
            if analysis:
                short = analysis[:200].replace("\n", " ")
                lines.append(f"  ניתוח: {short}")
    if declined:
        lines.append("\n### הגשות שנדחו (לקחים)")
        for name, analysis in declined[:MAX_HISTORY_ITEMS // 2]:
            lines.append(f"- **{name}**")
            if analysis:
                short = analysis[:200].replace("\n", " ")
                lines.append(f"  ניתוח: {short}")

    return "\n".join(lines)


def build_and_save(client) -> str:
    """Re-extract history from Monday and write to the learned section."""
    history = _extract_history(client)
    base = _load_file()
    updated = _inject_history(base, history)
    PROFILE_PATH.write_text(updated, encoding="utf-8")
    return history
