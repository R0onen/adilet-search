from adilet_ml.eval.metrics import (
    classification_bundle,
    metric_bundle,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)
from adilet_ml.retrieval.bm25 import BM25Index


def test_metrics() -> None:
    qrels = {"q1": {"a": 2, "b": 1}, "q2": {"c": 2}}
    run = {"q1": ["b", "a", "x"], "q2": ["x", "c"]}
    assert 0 < ndcg_at_k(qrels, run, 10) <= 1
    assert recall_at_k(qrels, run, 1) == 0.25
    assert mrr_at_k(qrels, run, 10) == 0.75
    assert set(metric_bundle(qrels, run)) == {"ndcg@10", "recall@10", "recall@50", "mrr@10"}


def test_classification_metrics() -> None:
    metrics = classification_bundle([1, 0, 1, 0], [0.9, 0.2, 0.8, 0.4])
    assert metrics["roc_auc"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["pr_auc"] == 1.0


def test_bm25_index() -> None:
    index = BM25Index().fit(
        [
            ("a1", "задержка заработной платы работодатель"),
            ("a2", "экологический штраф выбросы"),
            ("a3", "расторжение трудового договора"),
        ],
        "ru",
    )
    hits = index.search("ответственность за задержка заработной платы", top_k=2, lang="ru")
    assert hits
    assert hits[0].doc_id == "a1"
