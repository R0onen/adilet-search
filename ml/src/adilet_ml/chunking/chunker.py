"""Chunk legal articles into contract-shaped passage chunks."""

from __future__ import annotations

from collections.abc import Iterable


def count_tokens(text: str) -> int:
    return len(text.split())


def split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in text.splitlines() if part.strip()]


def chunk_paragraphs(paragraphs: list[str], max_tokens: int = 400) -> list[list[str]]:
    """Split at paragraph boundaries with one-paragraph overlap."""
    if not paragraphs:
        return [[]]
    chunks: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        tokens = count_tokens(paragraph)
        if current and current_tokens + tokens > max_tokens:
            chunks.append(current)
            current = current[-1:]
            current_tokens = sum(count_tokens(p) for p in current)
        current.append(paragraph)
        current_tokens += tokens
    if current:
        chunks.append(current)
    return chunks


def iter_text_chunks(text: str, max_tokens: int = 400) -> Iterable[str]:
    for paragraphs in chunk_paragraphs(split_paragraphs(text), max_tokens):
        yield "\n".join(paragraphs)


def embedding_header(short_title: str, number: str | None, title: str | None, lang: str) -> str:
    clean_title = title or ""
    if number is None:
        return f"{short_title}. {clean_title}".strip()
    marker = f"Article {number}" if lang not in {"ru", "kk"} else (
        f"Статья {number}" if lang == "ru" else f"{number}-бап"
    )
    return f"{short_title}. {marker}. {clean_title}".strip()
