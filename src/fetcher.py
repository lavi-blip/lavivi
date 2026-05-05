"""Fetch RFP content from a URL or local PDF/text file."""

from __future__ import annotations

from pathlib import Path

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

MAX_CHARS = 60_000


def fetch_url(url: str, timeout: int = 30) -> str:
    session = requests.Session()
    session.headers.update(HEADERS)
    response = session.get(url, timeout=timeout, allow_redirects=True)

    if response.status_code in (403, 401, 429):
        return _fetch_with_browser(url, timeout=timeout)

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return _extract_pdf_bytes(response.content)

    return _extract_html(response.text)


def _fetch_with_browser(url: str, timeout: int = 30) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ValueError(
            "נדרשת התקנה חד-פעמית: הרץ בPowerShell:\n"
            "python -m playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="he-IL",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(4000)
        # try to wait for meaningful content
        try:
            page.wait_for_selector("main, article, .content, #content, [role='main']",
                                   timeout=10_000)
        except Exception:
            pass
        text = page.inner_text("body")
        browser.close()

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)[:MAX_CHARS]


def read_file(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_bytes(path.read_bytes())
    if suffix in {".html", ".htm"}:
        return _extract_html(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")[:MAX_CHARS]


def _extract_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:MAX_CHARS]


def _extract_pdf_bytes(data: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)[:MAX_CHARS]
