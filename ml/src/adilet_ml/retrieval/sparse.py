"""Deterministic sparse BM25-style encoding for Qdrant sparse vectors."""

from __future__ import annotations

import math
import re
import zlib
from collections import Counter
from dataclasses import dataclass

from adilet_ml.schemas import SparseVector

TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)

RU_STOPWORDS = {
    "а",
    "в",
    "во",
    "и",
    "или",
    "к",
    "на",
    "не",
    "о",
    "об",
    "от",
    "по",
    "с",
    "со",
    "за",
    "для",
    "при",
    "что",
}

KK_STOPWORDS = {
    "және",
    "мен",
    "немесе",
    "үшін",
    "туралы",
    "бойынша",
    "осы",
    "бір",
}


def tokenize(text: str, lang: str | None = None) -> list[str]:
    """Lowercase tokenization with lightweight RU/KK stopword handling."""
    stopwords = KK_STOPWORDS if lang == "kk" else RU_STOPWORDS if lang == "ru" else set()
    tokens = [token.strip("-_").lower() for token in TOKEN_RE.findall(text)]
    return [token for token in tokens if token and token not in stopwords]


def stable_index(token: str) -> int:
    """Map a token to a stable uint32 id for Qdrant sparse vectors."""
    return zlib.crc32(token.encode("utf-8")) & 0xFFFFFFFF


@dataclass(frozen=True)
class SparseEncoder:
    """BM25 term-weight encoder.

    Qdrant applies IDF (`modifier: idf`), so this class emits TF saturation only.
    """

    k1: float = 1.2
    b: float = 0.75
    avgdl: float = 142.3

    def encode_query(self, text: str, lang: str | None = None) -> SparseVector:
        indices = sorted({stable_index(token) for token in tokenize(text, lang)})
        return SparseVector(indices=indices, values=[1.0] * len(indices))

    def encode_passage(self, text: str, lang: str | None = None) -> SparseVector:
        tokens = tokenize(text, lang)
        counts = Counter(tokens)
        dl = max(len(tokens), 1)
        weights: dict[int, float] = {}
        norm = self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-6))
        for token, tf in counts.items():
            weight = (tf * (self.k1 + 1.0)) / (tf + norm)
            index = stable_index(token)
            weights[index] = weights.get(index, 0.0) + float(weight)
        pairs = sorted(weights.items())
        return SparseVector(
            indices=[index for index, _ in pairs],
            values=[round(value, 6) for _, value in pairs],
        )


def lexical_overlap_score(query: str, text: str) -> float:
    """Simple stable reranking score used by the offline service fallback."""
    query_tokens = set(tokenize(query))
    text_tokens = tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0
    text_set = set(text_tokens)
    hits = len(query_tokens & text_set)
    coverage = hits / len(query_tokens)
    density = hits / math.sqrt(len(text_set))
    return round(coverage * 2.0 + density, 6)
