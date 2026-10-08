"""Parquet loading and validation against contracts/data_schema.md."""

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dev.sample_corpus import ARTICLE_SCHEMA, CHUNK_SCHEMA, DOCUMENT_SCHEMA, build, write
from indexer.corpus import CorpusError, load_corpus
from indexer.pipeline import chunk_payload, point_id


def _write(out: Path, documents: list[Any], articles: list[Any], chunks: list[Any]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for name, rows, schema in (
        ("documents", documents, DOCUMENT_SCHEMA),
        ("articles", articles, ARTICLE_SCHEMA),
        ("chunks", chunks, CHUNK_SCHEMA),
    ):
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), out / f"{name}.parquet")
    return out


def test_synthetic_corpus_is_valid(tmp_path: Path) -> None:
    corpus = load_corpus(write(tmp_path))
    assert (len(corpus.documents), len(corpus.articles), len(corpus.chunks)) == (6, 14, 16)
    assert corpus.corpus_version == "2026.10.08-synthetic"
    excluded = [a for a in corpus.articles if a["unit_status"] == "excluded"]
    assert {a["lang"] for a in excluded} == {"ru", "kk"}


def test_missing_file_and_column(tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "chunks.parquet").unlink()
    table = pq.read_table(tmp_path / "articles.parquet").drop_columns(["content_hash"])
    pq.write_table(table, tmp_path / "articles.parquet")
    with pytest.raises(CorpusError) as info:
        load_corpus(tmp_path)
    text = str(info.value)
    assert "missing file chunks.parquet" in text
    assert "missing column `content_hash`" in text


def test_wrong_type(tmp_path: Path) -> None:
    write(tmp_path)
    table = pq.read_table(tmp_path / "documents.parquet")
    table = table.set_column(
        table.schema.get_field_index("article_count"),
        "article_count",
        pa.array([str(v) for v in table["article_count"].to_pylist()]),
    )
    pq.write_table(table, tmp_path / "documents.parquet")
    with pytest.raises(CorpusError, match="`article_count` has type string, expected int"):
        load_corpus(tmp_path)


def test_semantic_problems_are_all_reported(tmp_path: Path) -> None:
    documents, articles, chunks = build()
    documents[0]["lang"] = "kz"
    articles[1]["article_id"] = "T0000000001:ru:wrong"
    articles[2]["unit_status"] = "deleted"
    articles[3]["has_amendments"] = not articles[3]["has_amendments"]
    chunks[0]["chunk_id"] = chunks[0]["chunk_id"] + "x"
    chunks[1]["text_for_embedding"] = "   "
    chunks[2]["doc_status"] = None
    with pytest.raises(CorpusError) as info:
        load_corpus(_write(tmp_path, documents, articles, chunks))
    text = str(info.value)
    for expected in (
        "`lang`='kz'",
        "article_id must be",
        "`unit_status`='deleted'",
        "has_amendments disagrees",
        "chunk_id must be",
        "empty text_for_embedding",
        "`doc_status` is null",
    ):
        assert expected in text, expected


def test_payload_and_point_id() -> None:
    _, _, chunks = build()
    chunk = next(c for c in chunks if c["chunk_id"] == "T0000000001:ru:a114:c1")
    payload = chunk_payload(chunk)
    assert set(payload) == {
        "chunk_id",
        "article_id",
        "doc_id",
        "lang",
        "doc_type",
        "doc_status",
        "unit_status",
        "adopted_date",
        "unit_number",
        "unit_title",
        "doc_short_title",
        "text",
        "text_for_embedding",
        "source_url",
    }
    assert payload["adopted_date"] == 20151123
    assert point_id("K1500000414:ru:a113:c0") == point_id("K1500000414:ru:a113:c0")
    assert point_id("K1500000414:ru:a113:c0") != point_id("K1500000414:ru:a113:c1")
