"""CLI entry point for the Lavivi RFP intake tool."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src import config
from src.analyzer import analyze_rfp
from src.crawler import crawl
from src.fetcher import fetch_url, read_file
from src.fit_checker import check_fit
from src.monday import (
    MondayClient,
    build_fit_report_column_values,
    build_main_column_values,
    build_requirement_column_values,
    build_subitem_column_values,
)
from src.preview import render_preview
from src import profile as org_profile_mod


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lavivi RFP intake tool")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--url", help="URL of the call-for-proposals page")
    src.add_argument("--file", help="Local PDF/HTML/text file to analyze")
    parser.add_argument("--deep", action="store_true",
                        help="Deep mode: crawl all sub-pages, assess fit, prepare content")
    parser.add_argument("--scan", action="store_true",
                        help="Routine mode: scan all platforms for new RFPs")
    parser.add_argument("--build-profile", action="store_true",
                        help="Re-extract org learnings from Monday and update org_profile.md")
    parser.add_argument("--executor",
                        help="Pre-assign subitems to this team member")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print analysis only; do not call Monday.com")
    parser.add_argument("--refresh-config", action="store_true",
                        help="Print live group/column IDs from Monday and exit")
    return parser.parse_args()


def _confirm(console: Console, prompt: str = "ליצור פריטים ב-Monday?") -> bool:
    answer = console.input(f"[bold]{prompt} [Y/n] [/bold]")
    return answer.strip().lower() in {"", "y", "yes", "כן"}


# ─── refresh-config ────────────────────────────────────────────────────────────

def _cmd_refresh_config(console: Console) -> int:
    client = MondayClient()
    console.print("[bold]קבוצות בלוח:[/bold]")
    for group in client.get_groups():
        console.print(f"  {group['id']}\t{group['title']}")
    return 0


# ─── build-profile ─────────────────────────────────────────────────────────────

def _cmd_build_profile(console: Console) -> int:
    client = MondayClient()
    console.print("[dim]שולף נתונים מהגשות קודמות במאנדיי...[/dim]")
    history = org_profile_mod.build_and_save(client)
    if history:
        console.print("[green]פרופיל הארגון עודכן ב-org_profile.md ✓[/green]")
    else:
        console.print("[yellow]לא נמצאו הגשות עם תוצאה בלוח (אושרה / נדחתה).[/yellow]")
    return 0


# ─── scan ──────────────────────────────────────────────────────────────────────

def _cmd_scan(console: Console, *, dry_run: bool, yes: bool, executor: str | None) -> int:
    from src.scanner import mark_seen, scan_all

    console.print("[dim]סורק פלטפורמות...[/dim]")
    found = scan_all()

    if not found:
        console.print("[green]אין קולות קוראים חדשים.[/green]")
        return 0

    table = Table(title=f"נמצאו {len(found)} קולות קוראים חדשים", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("שם")
    table.add_column("פלטפורמה")
    table.add_column("קישור")
    for i, rfp in enumerate(found, 1):
        table.add_row(str(i), rfp.title[:60], rfp.platform, rfp.url[:60])
    console.print(table)

    if dry_run:
        console.print("[yellow]Dry-run — לא נוצר שום דבר ב-Monday.[/yellow]")
        return 0

    if not yes and not _confirm(console, f"ליצור {len(found)} פריטי 'בדיקת התאמה' ב-Monday?"):
        console.print("[yellow]בוטל.[/yellow]")
        return 0

    client = MondayClient()
    group_id_cache: dict[str, str] = {}

    for rfp in found:
        group_title = (
            config.GROUP_TITLE_ISRAEL
            if rfp.category in {"ממשל / רשויות", "קרנות פילנתרופיות", "מגזר שלישי"}
            else config.GROUP_TITLE_ABROAD
        )
        if group_title not in group_id_cache:
            group_id_cache[group_title] = client.resolve_group_id(group_title)
        group_id = group_id_cache[group_title]

        item_id = client.create_item(
            group_id=group_id,
            item_name=rfp.title[:255],
            column_values={
                config.COL_REQUEST_TYPE: {"label": config.REQUEST_TYPE_VALUE},
                config.COL_OUR_STAGE: {"label": config.INITIAL_OUR_STAGE},
                config.COL_SOURCE: {"label": rfp.category},
                config.COL_SUBMISSION_ANALYSIS: {"text": f"מקור: {rfp.platform}\nקישור: {rfp.url}"},
            },
        )
        console.print(f"  [green]+[/green] {rfp.title[:60]} (id={item_id})")

    mark_seen(found)
    console.print(f"\n[green]נוצרו {len(found)} פריטים ב-Monday ✓[/green]")
    return 0


# ─── deep ──────────────────────────────────────────────────────────────────────

def _render_fit_report(report, console: Console) -> None:
    score_color = {"גבוה": "green", "בינוני": "yellow", "נמוך": "red", "לא מתאים": "red"}
    color = score_color.get(report.fit_score, "white")

    header = (
        f"[bold]{report.title_he}[/bold]\n"
        f"גוף: {report.funder or '—'} | "
        f"דדליין: [yellow]{report.deadline.isoformat()}[/yellow] | "
        f"התאמה: [{color}]{report.fit_score}[/{color}]\n\n"
        f"{report.recommendation_he}"
    )
    if report.disqualifiers:
        header += "\n\n[red]פסילות:[/red] " + " | ".join(report.disqualifiers)
    console.print(Panel(header, title="דו\"ח התאמה", border_style=color))

    auto = [r for r in report.requirements if r.is_autonomous]
    human = [r for r in report.requirements if not r.is_autonomous]

    if auto:
        t = Table(title=f"משימות אוטומטיות ({len(auto)})", show_lines=True)
        t.add_column("משימה"); t.add_column("סוג"); t.add_column("שעות"); t.add_column("ימים לפני")
        for r in auto:
            t.add_row(r.name_he, r.action_type, f"{r.estimated_hours:g}", str(r.days_before_deadline))
        console.print(t)

    if human:
        t = Table(title=f"משימות שדורשות אותך ({len(human)})", show_lines=True, border_style="yellow")
        t.add_column("משימה"); t.add_column("מה לעשות")
        for r in human:
            t.add_row(r.name_he, (r.human_instructions or "")[:80])
        console.print(t)

    if report.questions:
        console.print(Panel(
            f"יש {len(report.questions)} שאלות בבקשה — טיוטות תשובות יוזנו כ-Updates על הסאב-אייטמס.",
            border_style="cyan",
        ))


def _cmd_deep(
    url: str | None,
    file_path: str | None,
    console: Console,
    *,
    dry_run: bool,
    yes: bool,
    executor: str | None,
) -> int:
    if not url and not file_path:
        console.print("[red]חובה לציין --url או --file עבור --deep[/red]")
        return 2

    console.print("[dim]זוחל דפים קשורים...[/dim]")
    content = crawl(url) if url else read_file(file_path)
    if not content.strip():
        console.print("[red]לא נמצא תוכן.[/red]")
        return 1

    console.print("[dim]טוען פרופיל ארגון...[/dim]")
    org_profile = org_profile_mod.load()

    console.print("[dim]מנתח התאמה עם קלוד...[/dim]")
    report = check_fit(content, org_profile)
    _render_fit_report(report, console)

    if dry_run:
        console.print("[yellow]Dry-run — לא נוצר שום דבר ב-Monday.[/yellow]")
        return 0

    if not report.is_worth_submitting:
        console.print("[red]הכלי לא ממליץ להגיש. לבטל?[/red]")
        if not _confirm(console, "להמשיך בכל זאת וליצור פריט ב-Monday?"):
            return 0

    if not yes and not _confirm(console, "ליצור פריט + סאב-אייטמס + Updates ב-Monday?"):
        console.print("[yellow]בוטל.[/yellow]")
        return 0

    client = MondayClient()
    group_title = (
        config.GROUP_TITLE_ISRAEL if report.origin == "israel" else config.GROUP_TITLE_ABROAD
    )
    group_id = client.resolve_group_id(group_title)

    item_id = client.create_item(
        group_id=group_id,
        item_name=report.title_he,
        column_values=build_fit_report_column_values(report),
    )
    console.print(f"[green]נוצר פריט ראשי[/green] (id={item_id}) — {group_title}")

    req_ids: dict[int, str] = {}
    for i, req in enumerate(report.requirements):
        sub_id = client.create_subitem(
            parent_item_id=item_id,
            item_name=req.name_he,
            column_values=build_requirement_column_values(req, report.deadline, executor=executor),
        )
        req_ids[i] = sub_id
        tag = "[green]אוטו[/green]" if req.is_autonomous else "[yellow]ידני[/yellow]"
        console.print(f"  {tag} (id={sub_id}) — {req.name_he}")

        # Post prepared content / instructions as an Update on the subitem
        update_body = _format_update(req)
        if update_body:
            client.create_update(item_id=sub_id, body=update_body)

    # Post draft question-answers as updates on the *last* autonomous subitem,
    # or directly on the parent item if none exist.
    if report.questions:
        target_id = next(
            (req_ids[i] for i, r in enumerate(report.requirements) if r.is_autonomous),
            item_id,
        )
        qa_body = "## שאלות הבקשה — טיוטות תשובות\n\n" + "\n\n".join(
            f"**{q.question_he}**\n{q.draft_answer_he}" for q in report.questions
        )
        client.create_update(item_id=target_id, body=qa_body)
        console.print(f"  [cyan]+ {len(report.questions)} תשובות לשאלות הוזנו כ-Update[/cyan]")

    console.print(
        "\n[bold]משימות ידניות שנותרו:[/bold]\n"
        "  • POC — בחירת איש קשר מלוח Contacts\n"
        "  • Account — חיבור לחשבון בלוח Accounts\n"
        "  • נציג/ה — הקצאה לפי הצוות"
    )
    console.print(
        f"\nקישור: https://lavi-blip.monday.com/boards/{config.BOARD_ID}/pulses/{item_id}"
    )
    return 0


def _format_update(req) -> str:
    if req.is_autonomous and req.prepared_content:
        return f"## {req.name_he} — תוכן מוכן\n\n{req.prepared_content}"
    if not req.is_autonomous and req.human_instructions:
        return f"## {req.name_he} — נדרשת פעולה ידנית\n\n{req.human_instructions}"
    return ""


# ─── simple (original) mode ────────────────────────────────────────────────────

def _cmd_simple(
    url: str | None,
    file_path: str | None,
    console: Console,
    *,
    dry_run: bool,
    yes: bool,
    executor: str | None,
) -> int:
    if not url and not file_path:
        console.print("[red]חובה לציין --url או --file[/red]")
        return 2

    console.print("[dim]מוריד את תוכן הקול הקורא...[/dim]")
    content = fetch_url(url) if url else read_file(file_path)
    if not content.strip():
        console.print("[red]לא הצלחתי להוריד תוכן מהמקור.[/red]")
        return 1

    console.print("[dim]שולח לקלוד לניתוח...[/dim]")
    analysis = analyze_rfp(content)
    render_preview(analysis, console)

    if dry_run:
        console.print("[yellow]Dry-run — לא נוצר שום דבר ב-Monday.[/yellow]")
        return 0

    if not yes and not _confirm(console, "ליצור את הפריט והתת-משימות ב-Monday?"):
        console.print("[yellow]בוטל.[/yellow]")
        return 0

    client = MondayClient()
    group_title = (
        config.GROUP_TITLE_ISRAEL if analysis.origin == "israel" else config.GROUP_TITLE_ABROAD
    )
    group_id = client.resolve_group_id(group_title)

    item_id = client.create_item(
        group_id=group_id,
        item_name=analysis.title_he,
        column_values=build_main_column_values(analysis),
    )
    console.print(f"[green]נוצר פריט ראשי[/green] (id={item_id}) — {group_title}")

    for task in analysis.tasks:
        sub_id = client.create_subitem(
            parent_item_id=item_id,
            item_name=task.name_he,
            column_values=build_subitem_column_values(task, analysis.deadline, executor=executor),
        )
        console.print(f"  [green]+[/green] (id={sub_id}) — {task.name_he}")

    console.print(
        "\n[bold]משימות ידניות שנותרו:[/bold]\n"
        "  • POC / Account / נציג/ה"
    )
    console.print(
        f"\nקישור: https://lavi-blip.monday.com/boards/{config.BOARD_ID}/pulses/{item_id}"
    )
    return 0


# ─── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    load_dotenv()
    args = _parse_args()
    console = Console()

    if args.refresh_config:
        return _cmd_refresh_config(console)
    if args.build_profile:
        return _cmd_build_profile(console)
    if args.scan:
        return _cmd_scan(console, dry_run=args.dry_run, yes=args.yes, executor=args.executor)
    if args.deep:
        return _cmd_deep(args.url, args.file, console,
                         dry_run=args.dry_run, yes=args.yes, executor=args.executor)
    return _cmd_simple(args.url, args.file, console,
                       dry_run=args.dry_run, yes=args.yes, executor=args.executor)


if __name__ == "__main__":
    sys.exit(main())
