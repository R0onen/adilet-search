"""Polite fetcher and lightweight parser for adilet.zan.kz pages."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

ARTICLE_RU_RE = re.compile(r"^Статья\s+([0-9]+(?:-[0-9]+)?)\.?\s*(.*)$", re.IGNORECASE)
ARTICLE_KK_RE = re.compile(r"^([0-9]+(?:-[0-9]+)?)-бап\.?\s*(.*)$", re.IGNORECASE)
SECTION_RU_RE = re.compile(r"^(Раздел|Глава)\s+", re.IGNORECASE)
SECTION_KK_RE = re.compile(r"^(Бөлім|Тарау)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedArticle:
    unit_number: str
    unit_title: str
    text: str
    amendment_notes: list[str]
    unit_status: str


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    articles: list[ParsedArticle]


def adilet_url(doc_id: str, lang: str) -> str:
    prefix = "rus" if lang == "ru" else "kaz"
    return f"https://adilet.zan.kz/{prefix}/docs/{doc_id}"


def fetch_cached(
    doc_id: str,
    lang: str,
    cache_dir: Path,
    *,
    user_agent: str = "AdiletSearchML/0.1 educational crawler",
    min_delay_s: float = 1.0,
) -> Path:
    """Fetch a page once and cache it; callers control batch-level pacing."""
    out = cache_dir / lang / f"{doc_id}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    time.sleep(min_delay_s)
    request = urllib.request.Request(adilet_url(doc_id, lang), headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to fetch {doc_id}/{lang}: {exc}") from exc
    out.write_bytes(data)
    (out.with_suffix(".fetched_at.txt")).write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
    return out


def _visible_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _article_match(line: str, lang: str) -> re.Match[str] | None:
    return (ARTICLE_KK_RE if lang == "kk" else ARTICLE_RU_RE).match(line)


def _is_section(line: str, lang: str) -> bool:
    return bool((SECTION_KK_RE if lang == "kk" else SECTION_RU_RE).match(line))


def _is_note(line: str, lang: str) -> bool:
    lowered = line.lower()
    markers = ("ескерту", "алып тасталды") if lang == "kk" else ("сноска", "исключена")
    return lowered.startswith(markers)


def parse_html(html: str, lang: str) -> ParsedDocument:
    """Parse common Adilet article markers.

    This parser is intentionally conservative. It extracts articles by visible text markers and
    leaves difficult structure to QA rather than silently rewriting statute wording.
    """
    lines = _visible_lines(html)
    title = next((line for line in lines if not _is_section(line, lang)), "Untitled")
    articles: list[ParsedArticle] = []
    current_number: str | None = None
    current_title = ""
    body: list[str] = []
    notes: list[str] = []

    def flush() -> None:
        nonlocal body, notes, current_number, current_title
        if current_number is None:
            return
        text = "\n".join(body).strip()
        haystack = f"{current_title}\n{text}".lower()
        excluded = "алып тасталды" in haystack if lang == "kk" else "исключен" in haystack
        articles.append(
            ParsedArticle(
                unit_number=current_number,
                unit_title=current_title.strip() or None or "",
                text=text,
                amendment_notes=notes,
                unit_status="excluded" if excluded else "in_force",
            )
        )
        body = []
        notes = []

    for line in lines:
        match = _article_match(line, lang)
        if match:
            if current_number == match.group(1):
                body.append(line)
                continue
            flush()
            current_number = match.group(1)
            current_title = match.group(2).strip()
            continue
        if current_number is None or _is_section(line, lang):
            continue
        if _is_note(line, lang):
            notes.append(line)
        else:
            body.append(line)
    flush()
    return ParsedDocument(title=title, articles=articles)
