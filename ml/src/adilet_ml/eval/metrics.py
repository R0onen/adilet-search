"""Retrieval metrics used throughout ML reports."""

from __future__ import annotations

import math

Qrels = dict[str, dict[str, int]]
Run = dict[str, list[str]]


def dcg(relevances: list[int]) -> float:
    return sum((2**rel - 1) / math.log2(rank + 2) for rank, rel in enumerate(relevances))


def ndcg_at_k(qrels: Qrels, run: Run, k: int = 10) -> float:
    values: list[float] = []
    for query_id, labels in qrels.items():
        predicted = run.get(query_id, [])[:k]
        gains = [labels.get(doc_id, 0) for doc_id in predicted]
        ideal = sorted(labels.values(), reverse=True)[:k]
        ideal_dcg = dcg(ideal)
        values.append(0.0 if ideal_dcg == 0 else dcg(gains) / ideal_dcg)
    return _mean(values)


def recall_at_k(qrels: Qrels, run: Run, k: int = 10, positive_threshold: int = 1) -> float:
    values: list[float] = []
    for query_id, labels in qrels.items():
        positives = {doc_id for doc_id, rel in labels.items() if rel >= positive_threshold}
        if not positives:
            continue
        predicted = set(run.get(query_id, [])[:k])
        values.append(len(positives & predicted) / len(positives))
    return _mean(values)


def mrr_at_k(qrels: Qrels, run: Run, k: int = 10, positive_threshold: int = 1) -> float:
    values: list[float] = []
    for query_id, labels in qrels.items():
        rank_value = 0.0
        for rank, doc_id in enumerate(run.get(query_id, [])[:k], start=1):
            if labels.get(doc_id, 0) >= positive_threshold:
                rank_value = 1.0 / rank
                break
        values.append(rank_value)
    return _mean(values)


def metric_bundle(qrels: Qrels, run: Run) -> dict[str, float]:
    return {
        "ndcg@10": ndcg_at_k(qrels, run, 10),
        "recall@10": recall_at_k(qrels, run, 10),
        "recall@50": recall_at_k(qrels, run, 50),
        "mrr@10": mrr_at_k(qrels, run, 10),
    }


def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    positives = [score for label, score in zip(y_true, y_score, strict=True) if label == 1]
    negatives = [score for label, score in zip(y_true, y_score, strict=True) if label == 0]
    if not positives or not negatives:
        return 0.0
    wins = 0.0
    for pos in positives:
        for neg in negatives:
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def pr_auc(y_true: list[int], y_score: list[float]) -> float:
    positives = sum(y_true)
    if positives == 0:
        return 0.0
    ordered = sorted(zip(y_score, y_true, strict=True), reverse=True)
    precisions: list[float] = []
    hits = 0
    for rank, (_, label) in enumerate(ordered, start=1):
        if label == 1:
            hits += 1
            precisions.append(hits / rank)
    return _mean(precisions)


def f1_at_threshold(y_true: list[int], y_score: list[float], threshold: float = 0.5) -> float:
    y_pred = [1 if score >= threshold else 0 for score in y_score]
    tp = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == pred == 1)
    fp = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == 0 and pred == 1)
    fn = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == 1 and pred == 0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def classification_bundle(
    y_true: list[int], y_score: list[float], threshold: float = 0.5
) -> dict[str, float]:
    return {
        "roc_auc": roc_auc(y_true, y_score),
        "f1": f1_at_threshold(y_true, y_score, threshold),
        "pr_auc": pr_auc(y_true, y_score),
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
