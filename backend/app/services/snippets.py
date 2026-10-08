"""Result snippets (≤ 300 chars) and highlight offsets (contracts/api.md `SearchResult`).

The snippet is a verbatim excerpt of the best chunk: the sentence window with the most query-term
overlap. Terms are matched by a crude prefix stem, which is enough for Russian and Kazakh
inflection in a UI highlight (it is not used for ranking). Statute text is never altered; an
ellipsis marks a cut.
"""

import re
from dataclasses import dataclass

SNIPPET_MAX_CHARS = 300
ELLIPSIS = "…"
MIN_TERM_CHARS = 3

_WORD = re.compile(r"\w+", re.UNICODE)
# Sentence ends: punctuation followed by whitespace, or a line break.
_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+|\n+")


def stem(word: str) -> str:
    word = word.lower()
    return word if len(word) <= 4 else word[: max(4, len(word) - 3)]


def query_stems(query: str) -> set[str]:
    return {stem(w) for w in _WORD.findall(query) if len(w) >= MIN_TERM_CHARS}


def _matches(word: str, stems: set[str]) -> bool:
    lowered = word.lower()
    return len(lowered) >= MIN_TERM_CHARS and any(lowered.startswith(s) for s in stems)


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int


def _sentences(text: str) -> list[Span]:
    spans = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        if match.start() > start:
            spans.append(Span(start, match.start()))
        start = match.end()
    if start < len(text):
        spans.append(Span(start, len(text)))
    return spans


def _score(text: str, span: Span, stems: set[str]) -> int:
    words = _WORD.findall(text[span.start : span.end])
    return len({s for w in words for s in stems if w.lower().startswith(s)})


def _cut_window(text: str, center: int, limit: int) -> tuple[int, int]:
    """A window of at most `limit` chars around `center`, cut at word boundaries."""
    start = max(0, center - limit // 3)
    end = min(len(text), start + limit)
    start = max(0, end - limit)
    if start > 0:
        space = text.find(" ", start)
        if 0 <= space < center:
            start = space + 1
    if end < len(text):
        space = text.rfind(" ", start, end)
        if space > center:
            end = space
    return start, end


def make_snippet(text: str, query: str, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    stems = query_stems(query)
    sentences = _sentences(text) or [Span(0, len(text))]
    best = max(range(len(sentences)), key=lambda i: (_score(text, sentences[i], stems), -i))
    start, end = sentences[best].start, sentences[best].end

    budget = max_chars - 2 * len(ELLIPSIS)
    if end - start > budget:
        # One long sentence: centre a window on its first matching word.
        first_hit = next(
            (
                start + m.start()
                for m in _WORD.finditer(text[start:end])
                if _matches(m.group(), stems)
            ),
            start,
        )
        start, end = _cut_window(text, first_hit, budget)
    else:
        # Grow the window with neighbouring sentences while it fits.
        lo, hi = best, best
        while True:
            grown = False
            if hi + 1 < len(sentences) and sentences[hi + 1].end - start <= budget:
                hi += 1
                end = sentences[hi].end
                grown = True
            if lo > 0 and end - sentences[lo - 1].start <= budget:
                lo -= 1
                start = sentences[lo].start
                grown = True
            if not grown:
                break

    snippet = text[start:end].strip()
    prefix = ELLIPSIS if start > 0 else ""
    suffix = ELLIPSIS if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"[:max_chars]


def highlights(snippet: str, query: str) -> list[Span]:
    """Character offsets (start inclusive, end exclusive) of query terms found in `snippet`."""
    stems = query_stems(query)
    if not stems:
        return []
    return [Span(m.start(), m.end()) for m in _WORD.finditer(snippet) if _matches(m.group(), stems)]
