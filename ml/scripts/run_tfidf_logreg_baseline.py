"""Run a small TF-IDF + logistic-regression reranking baseline without sklearn."""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from adilet_ml.eval.metrics import Qrels, classification_bundle, metric_bundle
from adilet_ml.retrieval.bm25 import BM25Index
from adilet_ml.retrieval.sparse import tokenize


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _load_qrels(path: Path) -> Qrels:
    qrels: Qrels = defaultdict(dict)
    for row in _read_jsonl(path):
        qrels[str(row["query_id"])][str(row["article_id"])] = int(row["relevance"])
    return dict(qrels)


class TinyTfidf:
    def __init__(self, max_features: int = 4096) -> None:
        self.max_features = max_features
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray = np.zeros(0, dtype=np.float32)

    def fit(self, texts: list[str], lang: str | None = None) -> TinyTfidf:
        dfs: Counter[str] = Counter()
        freqs: Counter[str] = Counter()
        for text in texts:
            tokens = tokenize(text, lang)
            freqs.update(tokens)
            dfs.update(set(tokens))
        terms = [term for term, _ in freqs.most_common(self.max_features)]
        self.vocab = {term: idx for idx, term in enumerate(terms)}
        n_docs = max(len(texts), 1)
        self.idf = np.array(
            [math.log((1 + n_docs) / (1 + dfs[term])) + 1.0 for term in terms],
            dtype=np.float32,
        )
        return self

    def transform_one(self, text: str, lang: str | None = None) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        counts = Counter(token for token in tokenize(text, lang) if token in self.vocab)
        if not counts:
            return vec
        for token, count in counts.items():
            vec[self.vocab[token]] = count
        vec *= self.idf
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def _pair_features(
    query: dict[str, Any],
    article: dict[str, Any],
    vectorizer: TinyTfidf,
    bm25_score: float,
) -> list[float]:
    lang = str(query["lang"])
    q_vec = vectorizer.transform_one(str(query["text"]), lang)
    d_vec = vectorizer.transform_one(str(article["text"]), lang)
    q_tokens = set(tokenize(str(query["text"]), lang))
    d_tokens = set(tokenize(str(article["text"]), lang))
    overlap = len(q_tokens & d_tokens) / max(len(q_tokens), 1)
    return [
        _cosine(q_vec, d_vec),
        overlap,
        bm25_score,
        math.log1p(len(str(query["text"]))),
        math.log1p(len(str(article["text"]))),
    ]


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -40, 40)))


def _fit_logreg(x_train: np.ndarray, y_train: np.ndarray, epochs: int, lr: float) -> np.ndarray:
    x_bias = np.column_stack([np.ones(len(x_train)), x_train])
    weights = np.zeros(x_bias.shape[1], dtype=np.float64)
    positives = max(float(y_train.sum()), 1.0)
    negatives = max(float(len(y_train) - y_train.sum()), 1.0)
    sample_weight = np.where(
        y_train == 1,
        len(y_train) / (2 * positives),
        len(y_train) / (2 * negatives),
    )
    for _ in range(epochs):
        pred = _sigmoid(x_bias @ weights)
        grad = (x_bias.T @ ((pred - y_train) * sample_weight)) / sample_weight.sum()
        grad[1:] += 0.001 * weights[1:]
        weights -= lr * grad
    return weights


def _predict(x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return _sigmoid(np.column_stack([np.ones(len(x)), x]) @ weights)


def _standardize(x_train: np.ndarray, x_all: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std == 0] = 1.0
    return (x_train - mean) / std, (x_all - mean) / std


def _split_query_ids(
    splits_path: Path | None, queries: list[dict[str, Any]]
) -> dict[str, set[str]]:
    if not splits_path or not splits_path.exists():
        ids = {str(row["query_id"]) for row in queries}
        return {"train": ids, "val": ids, "test": ids}
    data = json.loads(splits_path.read_text(encoding="utf-8"))
    query_splits = data.get("synthetic_query_splits", {})
    return {
        "train": set(query_splits.get("train", [])),
        "val": set(query_splits.get("val", [])),
        "test": set(query_splits.get("test", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--queries", type=Path, default=Path("data/eval/queries.jsonl"))
    parser.add_argument("--qrels", type=Path, default=Path("data/eval/qrels.jsonl"))
    parser.add_argument("--splits", type=Path, default=Path("data/eval/splits.json"))
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("ml/experiments/20261008_tfidf_logreg_seed"),
    )
    parser.add_argument("--epochs", type=int, default=600)
    parser.add_argument("--lr", type=float, default=0.35)
    args = parser.parse_args(argv)

    queries = _read_jsonl(args.queries)
    qrels = _load_qrels(args.qrels)
    articles = pq.read_table(args.data_dir / "articles.parquet").to_pylist()
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in articles:
        by_lang[str(article["lang"])].append(article)

    vectorizer = TinyTfidf().fit(
        [str(row["text"]) for row in articles] + [str(row["text"]) for row in queries]
    )
    bm25 = {
        lang: BM25Index().fit(
            [(str(row["article_id"]), str(row["text"])) for row in lang_articles],
            lang,
        )
        for lang, lang_articles in by_lang.items()
    }
    splits = _split_query_ids(args.splits, queries)

    pairs: list[tuple[str, str, list[float], int]] = []
    for query in queries:
        lang = str(query["lang"])
        score_map = {
            hit.doc_id: hit.score
            for hit in bm25[lang].search(str(query["text"]), 100, lang)
        }
        for article in by_lang[lang]:
            article_id = str(article["article_id"])
            relevance = qrels.get(str(query["query_id"]), {}).get(article_id, 0)
            label = 1 if relevance >= 1 else 0
            features = _pair_features(query, article, vectorizer, score_map.get(article_id, 0.0))
            pairs.append((str(query["query_id"]), article_id, features, label))

    train_ids = splits["train"] or {query_id for query_id, *_ in pairs}
    x_all = np.array([features for _, _, features, _ in pairs], dtype=np.float64)
    y_all = np.array([label for *_, label in pairs], dtype=np.float64)
    train_mask = np.array([query_id in train_ids for query_id, *_ in pairs])
    x_train, x_scaled = _standardize(x_all[train_mask], x_all)
    y_train = y_all[train_mask]
    weights = _fit_logreg(x_train, y_train, args.epochs, args.lr)
    scores = _predict(x_scaled, weights)

    run: dict[str, list[tuple[str, float]]] = defaultdict(list)
    y_true = [int(value) for value in y_all]
    y_score = [float(value) for value in scores]
    for (query_id, article_id, _, _), score in zip(pairs, scores, strict=True):
        run[query_id].append((article_id, float(score)))
    ranked_run = {
        query_id: [
            article_id
            for article_id, _ in sorted(items, key=lambda item: (-item[1], item[0]))
        ]
        for query_id, items in run.items()
    }

    metrics = {
        "model": "tfidf_logreg_seed",
        "queries": len(queries),
        "candidate_pairs": len(pairs),
        **classification_bundle(y_true, y_score),
        **metric_bundle(qrels, ranked_run),
    }
    for split_name in ("train", "val", "test"):
        ids = splits[split_name]
        if not ids:
            continue
        split_qrels = {qid: labels for qid, labels in qrels.items() if qid in ids}
        split_run = {qid: ranked_run[qid] for qid in ids if qid in ranked_run}
        for metric, value in metric_bundle(split_qrels, split_run).items():
            metrics[f"{split_name}_{metric}"] = value

    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.run_dir / "config.yaml").write_text(
        "\n".join(
            [
                "model: tfidf_logreg_seed",
                "features: [tfidf_cosine, token_overlap, bm25_score, query_len, doc_len]",
                f"epochs: {args.epochs}",
                f"learning_rate: {args.lr}",
                "l2: 0.001",
                f"train_queries: {sorted(train_ids)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.run_dir / "env.json").write_text(
        json.dumps(
            {
                "python": sys.version,
                "platform": platform.platform(),
                "numpy": np.__version__,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
