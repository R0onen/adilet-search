import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location(
    "research_core", Path(__file__).parents[1] / "scripts/research_core.py"
)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def test_ranking_excludes_other_languages_and_collapses_duplicate_articles():
    chunks = [
        {"chunk_id": "b", "article_id": "A", "lang": "ru"},
        {"chunk_id": "c", "article_id": "A", "lang": "ru"},
        {"chunk_id": "d", "article_id": "B", "lang": "kk"},
        {"chunk_id": "a", "article_id": "C", "lang": "ru"},
    ]
    assert core.article_ranking(np.array([0.5, 0.6, 0.9, 0.6]), chunks, "ru") == ["C", "A"]


def test_paired_bootstrap_is_zero_for_identical_rankings_and_seeded():
    labels = {"q1": {"a": 1}, "q2": {"b": 1}}
    run = {"q1": ["a"], "q2": ["c", "b"]}
    assert core.bootstrap_delta(labels, run, run) == {"mean": 0.0, "ci95": [0.0, 0.0]}
    better = {"q1": ["a"], "q2": ["b"]}
    first = core.bootstrap_delta(labels, run, better)
    assert first == core.bootstrap_delta(labels, run, better)
    assert first["mean"] > 0


def test_bootstrap_keeps_parallel_language_queries_in_one_cluster():
    labels = {"ru": {"D:ru:a1": 1}, "kk": {"D:kk:a1": 1}}
    baseline = {"ru": ["D:ru:a1"], "kk": ["wrong"]}
    challenger = {"ru": ["wrong"], "kk": ["D:kk:a1"]}
    assert core.bootstrap_delta(labels, baseline, challenger) == {"mean": 0.0, "ci95": [0.0, 0.0]}
