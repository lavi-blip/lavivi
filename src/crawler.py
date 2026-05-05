"""BFS web crawler — follows relevant links from a starting URL.

Stays within the same domain. Also follows off-domain direct PDF/DOC links
that appear to be part of the same RFP package (e.g. application form, budget
template, terms of reference).
"""

from __future__ import annotations

from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .fetcher import HEADERS, MAX_CHARS, _extract_html, _extract_pdf_bytes


# Anchor-text / path fragments that suggest an RFP-related sub-page.
_RELEVANT_KEYWORDS = {
    "קול", "קורא", "מכרז", "מענק", "תנאים", "הגשה", "טופס", "בקשה",
    "נספח", "appendix", "tender", "grant", "rfp", "guidelines", "eligibility",
    "criteria", "application", "form", "budget", "template", "terms",
    "requirements", "call", "proposal",
}

_PDF_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}

MAX_PAGES = 25
MAX_CHARS_TOTAL = 120_000


def crawl(start_url: str, *, timeout: int = 30) -> str:
    """Return combined text from the starting URL and all related sub-pages."""
    base = urlparse(start_url)
    base_domain = base.netloc

    visited: set[str] = set()
    queue: deque[str] = deque([start_url])
    parts: list[str] = []
    total_chars = 0

    while queue and len(visited) < MAX_PAGES and total_chars < MAX_CHARS_TOTAL:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        content_type = resp.headers.get("Content-Type", "").lower()
        parsed = urlparse(url)
        ext = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""

        if "pdf" in content_type or ext in {"pdf"}:
            text = _extract_pdf_bytes(resp.content)
        elif "html" in content_type or not ext or ext in {"htm", "html", "php", "asp", "aspx"}:
            text = _extract_html(resp.text)
            # Enqueue relevant sub-links
            for link in _extract_links(resp.text, url, base_domain):
                if link not in visited:
                    queue.append(link)
        else:
            continue

        if text.strip():
            parts.append(f"--- דף: {url} ---\n{text}")
            total_chars += len(text)

    return "\n\n".join(parts)[:MAX_CHARS_TOTAL]


def _extract_links(html: str, base_url: str, base_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Same domain — include if path/text looks relevant
        if parsed.netloc == base_domain:
            anchor_text = (tag.get_text() or "").lower()
            path_lower = parsed.path.lower()
            if _is_relevant(anchor_text, path_lower):
                links.append(full_url)
        else:
            # Off-domain: only follow direct document files that look RFP-related
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in _PDF_EXTENSIONS):
                anchor_text = (tag.get_text() or "").lower()
                if _is_relevant(anchor_text, path_lower):
                    links.append(full_url)

    return links


def _is_relevant(anchor_text: str, path: str) -> bool:
    combined = anchor_text + " " + path
    return any(kw in combined for kw in _RELEVANT_KEYWORDS)
