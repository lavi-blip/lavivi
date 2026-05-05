"""Routine scanner — checks all platforms in sources.yaml for new RFPs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup

from .fetcher import HEADERS

SOURCES_PATH = Path(__file__).parent.parent / "sources.yaml"
SEEN_PATH = Path(__file__).parent.parent / ".seen_rfps.json"


@dataclass
class ScannedRfp:
    title: str
    url: str
    platform: str
    category: str


def scan_all() -> list[ScannedRfp]:
    """Scan every platform in sources.yaml and return unseen RFPs."""
    sources = _load_sources()
    seen = _load_seen()
    found: list[ScannedRfp] = []

    for platform in sources.get("platforms", []):
        name = platform["name"]
        url = platform["url"]
        category = platform.get("category", "כללי")
        ptype = platform.get("type", "html")

        try:
            items = _scrape_html(platform) if ptype == "html" else _scrape_rss(url)
        except Exception as exc:
            print(f"  [scan] שגיאה ב-{name}: {exc}")
            continue

        for item in items:
            key = item.url
            if key and key not in seen:
                found.append(ScannedRfp(
                    title=item.title or name,
                    url=key,
                    platform=name,
                    category=category,
                ))

    return found


def mark_seen(rfps: list[ScannedRfp]) -> None:
    seen = _load_seen()
    for rfp in rfps:
        seen[rfp.url] = rfp.title
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_sources() -> dict[str, Any]:
    if not SOURCES_PATH.exists():
        return {"platforms": []}
    return yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8")) or {}


def _load_seen() -> dict[str, str]:
    if not SEEN_PATH.exists():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


@dataclass
class _RawItem:
    title: str
    url: str


def _scrape_html(platform: dict) -> list[_RawItem]:
    url = platform["url"]
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    item_selector = platform.get("item_selector", "article")
    title_selector = platform.get("title_selector", "h3")
    link_selector = platform.get("link_selector", "a")

    items: list[_RawItem] = []
    for container in soup.select(item_selector)[:50]:
        title_tag = container.select_one(title_selector)
        link_tag = container.select_one(link_selector)

        title = (title_tag.get_text(strip=True) if title_tag else "").strip()
        href = link_tag["href"] if link_tag and link_tag.get("href") else ""

        if not href:
            continue

        if href.startswith("http"):
            full_url = href
        else:
            from urllib.parse import urljoin
            full_url = urljoin(url, href)

        if title or full_url:
            items.append(_RawItem(title=title or full_url, url=full_url))

    # Fallback: scan all links that contain RFP-ish keywords
    if not items:
        rfp_keywords = {"קול", "קורא", "מענק", "מכרז", "tender", "grant", "call"}
        for a in soup.find_all("a", href=True)[:200]:
            text = a.get_text(strip=True).lower()
            href = a["href"]
            if any(kw in text or kw in href.lower() for kw in rfp_keywords):
                from urllib.parse import urljoin
                full_url = href if href.startswith("http") else urljoin(url, href)
                items.append(_RawItem(title=a.get_text(strip=True), url=full_url))

    return items


def _scrape_rss(feed_url: str) -> list[_RawItem]:
    try:
        import feedparser  # type: ignore
    except ImportError:
        return []
    feed = feedparser.parse(feed_url)
    return [
        _RawItem(title=entry.get("title", ""), url=entry.get("link", ""))
        for entry in feed.entries[:50]
    ]
