import math
import subprocess
import sys

from adilet_ml.retrieval.sparse import SparseEncoder, lexical_overlap_score, stable_index, tokenize


def test_tokenize_and_stable_index() -> None:
    assert "и" not in tokenize("Работник и работодатель", "ru")
    assert "және" not in tokenize("қызметкер және жұмыс беруші", "kk")
    assert 0 <= stable_index("зарплата") < 2**32


def test_sparse_query_is_deterministic_across_processes() -> None:
    code = "from adilet_ml.retrieval.sparse import stable_index; print(stable_index('зарплата'))"
    first = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
    second = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
    assert first == second


def test_sparse_passage_weights() -> None:
    vector = SparseEncoder(k1=1.2, b=0.75, avgdl=5).encode_passage("зарплата зарплата труд")
    assert vector.indices == sorted(vector.indices)
    assert len(vector.indices) == len(vector.values) == 2
    assert all(value > 0 for value in vector.values)


def test_overlap_score_prefers_shared_terms() -> None:
    query = "задержка заработной платы"
    good = lexical_overlap_score(query, "задержка заработной платы работодателем")
    bad = lexical_overlap_score(query, "экологический штраф")
    assert good > bad
    assert math.isclose(lexical_overlap_score("", "text"), 0.0)
