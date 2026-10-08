"""Small BM25 baseline used by A2 notebooks and smoke tests."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from adilet_ml.retrieval.sparse import tokenize


@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    score: float


class BM25Index:
    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_lens: list[int] = []
        self.term_freqs: list[Counter[str]] = []
        self.doc_freq: Counter[str] = Counter()
        self.avgdl = 0.0

    def fit(self, docs: list[tuple[str, str]], lang: str | None = None) -> BM25Index:
        self.doc_ids = []
        self.doc_lens = []
        self.term_freqs = []
        self.doc_freq = Counter()
        for doc_id, text in docs:
            tokens = tokenize(text, lang)
            counts = Counter(tokens)
            self.doc_ids.append(doc_id)
            self.doc_lens.append(len(tokens))
            self.term_freqs.append(counts)
            self.doc_freq.update(counts.keys())
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0.0
        return self

    def search(self, query: str, top_k: int = 10, lang: str | None = None) -> list[SearchHit]:
        query_terms = tokenize(query, lang)
        scores: defaultdict[int, float] = defaultdict(float)
        n_docs = max(len(self.doc_ids), 1)
        for term in query_terms:
            df = self.doc_freq.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for idx, counts in enumerate(self.term_freqs):
                tf = counts.get(term, 0)
                if tf == 0:
                    continue
                dl = self.doc_lens[idx] or 1
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                scores[idx] += idf * (tf * (self.k1 + 1)) / denom
        hits = [SearchHit(self.doc_ids[idx], score) for idx, score in scores.items()]
        hits.sort(key=lambda hit: (-hit.score, hit.doc_id))
        return hits[:top_k]
