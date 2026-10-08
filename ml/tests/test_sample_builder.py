from pathlib import Path

import pyarrow.parquet as pq

from adilet_ml.data.sample_builder import build, write


def test_build_sample_rows() -> None:
    documents, articles, chunks = build()
    assert len(documents) == 2
    assert len(articles) == 30
    assert len(chunks) > len(articles)
    assert {doc["lang"] for doc in documents} == {"ru", "kk"}
    excluded = [article for article in articles if article["unit_status"] == "excluded"]
    assert {article["lang"] for article in excluded} == {"ru", "kk"}
    amended = [article for article in articles if article["has_amendments"]]
    assert {article["unit_number"] for article in amended} == {"113"}
    long_chunks = [chunk for chunk in chunks if chunk["article_id"].endswith(":a114")]
    assert len(long_chunks) >= 4


def test_write_sample_files(tmp_path: Path) -> None:
    manifest = write(tmp_path)
    assert manifest["row_counts"]["documents"] == 2
    assert manifest["row_counts"]["articles"] == 30
    for filename in ("documents.parquet", "articles.parquet", "chunks.parquet"):
        assert (tmp_path / filename).exists()
        assert pq.read_table(tmp_path / filename).num_rows > 0
    assert (tmp_path / "sample_articles.json").exists()
    article_table = pq.read_table(tmp_path / "articles.parquet")
    assert article_table["text"].null_count == 0
    assert article_table["amendment_notes"].null_count == 0
