"""CLI entry point for the Lavivi RFP intake tool."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from rich.console import Console

from src import config
from src.analyzer import analyze_rfp
from src.fetcher import fetch_url, read_file
from src.monday import (
    MondayClient,
    build_main_column_values,
    build_subitem_column_values,
)
from src.preview import render_preview


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lavivi RFP intake tool")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--url", help="URL of the call-for-proposals page")
    src.add_argument("--file", help="Local PDF/HTML/text file to analyze")
    parser.add_argument(
        "--executor",
        help="Pre-assign all subitems to this team member (matches dropdown_mkxrnxep label)",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print analysis only; do not call Monday.com",
    )
    parser.add_argument(
        "--refresh-config",
        action="store_true",
        help="Print the live group/column IDs from Monday and exit",
    )
    return parser.parse_args()


def _confirm(console: Console) -> bool:
    answer = console.input("[bold]ליצור את הפריט והתת-משימות ב-Monday? [Y/n] [/bold]")
    return answer.strip().lower() in {"", "y", "yes", "כן"}


def _refresh_config(console: Console) -> int:
    client = MondayClient()
    console.print("[bold]קבוצות בלוח:[/bold]")
    for group in client.get_groups():
        console.print(f"  {group['id']}\t{group['title']}")
    return 0


def main() -> int:
    load_dotenv()
    args = _parse_args()
    console = Console()

    if args.refresh_config:
        return _refresh_config(console)

    if not args.url and not args.file:
        console.print("[red]חובה לציין --url או --file[/red]")
        return 2

    console.print("[dim]מוריד את תוכן הקול הקורא...[/dim]")
    content = fetch_url(args.url) if args.url else read_file(args.file)
    if not content.strip():
        console.print("[red]לא הצלחתי להוריד תוכן מהמקור.[/red]")
        return 1

    console.print("[dim]שולח לקלוד לניתוח...[/dim]")
    analysis = analyze_rfp(content)
    render_preview(analysis, console)

    if args.dry_run:
        console.print("[yellow]Dry-run — לא נוצר שום דבר ב-Monday.[/yellow]")
        return 0

    if not args.yes and not _confirm(console):
        console.print("[yellow]בוטל. לא נוצר שום דבר ב-Monday.[/yellow]")
        return 0

    client = MondayClient()
    group_title = (
        config.GROUP_TITLE_ISRAEL
        if analysis.origin == "israel"
        else config.GROUP_TITLE_ABROAD
    )
    group_id = client.resolve_group_id(group_title)

    item_id = client.create_item(
        group_id=group_id,
        item_name=analysis.title_he,
        column_values=build_main_column_values(analysis),
    )
    console.print(f"[green]נוצר פריט ראשי[/green] (id={item_id}) בקבוצה: {group_title}")

    for task in analysis.tasks:
        sub_id = client.create_subitem(
            parent_item_id=item_id,
            item_name=task.name_he,
            column_values=build_subitem_column_values(
                task, analysis.deadline, executor=args.executor
            ),
        )
        console.print(f"  [green]+ תת-משימה[/green] (id={sub_id}) — {task.name_he}")

    console.print(
        "\n[bold]משימות ידניות שנותרו:[/bold]\n"
        "  • POC — בחירת איש קשר מלוח Contacts\n"
        "  • Account — חיבור לחשבון בלוח Accounts\n"
        "  • נציג/ה — הקצאה לפי הצוות"
    )
    console.print(
        f"\nקישור לפריט: https://lavi-blip.monday.com/boards/{config.BOARD_ID}/pulses/{item_id}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
