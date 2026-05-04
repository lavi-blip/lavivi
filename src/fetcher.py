"""Fetch RFP content from a URL or local PDF/text file."""

from __future__ import annotations

from pathlib import Path

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LaviviRfpIntake/1.0; "
        "+https://github.com/lavi-blip/lavivi)"
    ),
    "Accept-Language": "he,en;q=0.8",
}

MAX_CHARS = 60_000


def fetch_url(url: str, timeout: int = 30) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return _extract_pdf_bytes(response.content)

    return _extract_html(response.text)


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
