"""Render the analyzed RFP for the user to confirm before pushing to Monday."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import config
from .models import RfpAnalysis


def render_preview(analysis: RfpAnalysis, console: Console | None = None) -> None:
    console = console or Console()

    group = (
        config.GROUP_TITLE_ISRAEL
        if analysis.origin == "israel"
        else config.GROUP_TITLE_ABROAD
    )

    header = (
        f"[bold]{analysis.title_he}[/bold]\n"
        f"גוף מפרסם: {analysis.funder or '—'}\n"
        f"קבוצה: {group}\n"
        f"מקור: {analysis.source_category}\n"
        f"מועד אחרון להגשה: [yellow]{analysis.deadline.isoformat()}[/yellow]\n"
        f"סכום מבוקש: "
        + (
            f"${analysis.requested_amount_usd:,.0f}"
            if analysis.requested_amount_usd is not None
            else "—"
        )
    )
    console.print(Panel(header, title="פריט ראשי", border_style="cyan"))
    console.print(
        Panel(
            analysis.submission_analysis_he,
            title="Submission Analysis",
            border_style="magenta",
        )
    )

    table = Table(title="תת-משימות", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("שם המשימה")
    table.add_column("סוג פעולה")
    table.add_column("שעות", justify="right")
    table.add_column("ימים לפני דדליין", justify="right")
    table.add_column("תאריך יעד")

    for idx, task in enumerate(analysis.tasks, start=1):
        table.add_row(
            str(idx),
            task.name_he,
            task.action_type,
            f"{task.estimated_hours:g}",
            str(task.days_before_deadline),
            task.due_date(analysis.deadline).isoformat(),
        )
    console.print(table)
