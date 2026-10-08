"""PyArrow schemas and validation for `contracts/data_schema.md`."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

LANGS = {"ru", "kk"}
DOC_TYPES = {"code", "law", "decree", "resolution", "order", "other"}
DOC_STATUSES = {"in_force", "repealed", "not_yet_in_force"}
UNIT_TYPES = {"article", "paragraph", "chapter", "preamble", "annex"}
UNIT_STATUSES = {"in_force", "excluded"}
UNIT_KEY_RE = re.compile(r"^[a-z0-9-]+$")

DOCUMENT_SCHEMA = pa.schema(
    [
        ("doc_id", pa.string()),
        ("lang", pa.string()),
        ("title", pa.string()),
        ("short_title", pa.string()),
        ("doc_type", pa.string()),
        ("number", pa.string()),
        ("adopted_date", pa.date32()),
        ("revision_date", pa.date32()),
        ("status", pa.string()),
        ("source_url", pa.string()),
        ("article_count", pa.int32()),
        ("scraped_at", pa.timestamp("us", tz="UTC")),
        ("corpus_version", pa.string()),
    ]
)

ARTICLE_FIELDS = [
    ("article_id", pa.string()),
    ("doc_id", pa.string()),
    ("lang", pa.string()),
    ("unit_type", pa.string()),
    ("unit_key", pa.string()),
    ("unit_number", pa.string()),
    ("unit_title", pa.string()),
    ("unit_order", pa.int32()),
    ("unit_status", pa.string()),
    ("section_title", pa.string()),
    ("chapter_title", pa.string()),
    ("has_amendments", pa.bool_()),
    ("source_url", pa.string()),
    ("parallel_article_id", pa.string()),
    ("content_hash", pa.string()),
]

ARTICLE_SCHEMA = pa.schema(
    [
        *ARTICLE_FIELDS,
        ("text", pa.string()),
        ("amendment_notes", pa.list_(pa.string())),
    ]
)

CHUNK_SCHEMA = pa.schema(
    [
        *ARTICLE_FIELDS,
        ("chunk_id", pa.string()),
        ("chunk_index", pa.int16()),
        ("chunk_count", pa.int16()),
        ("text", pa.string()),
        ("text_for_embedding", pa.string()),
        ("doc_title", pa.string()),
        ("doc_short_title", pa.string()),
        ("doc_type", pa.string()),
        ("doc_status", pa.string()),
        ("adopted_date", pa.date32()),
        ("revision_date", pa.date32()),
        ("char_len", pa.int32()),
        ("token_len", pa.int32()),
        ("chunking_version", pa.string()),
        ("corpus_version", pa.string()),
    ]
)


class SchemaError(ValueError):
    """Raised when corpus rows do not match the data contract."""


@dataclass(frozen=True)
class CorpusTables:
    documents: list[dict[str, Any]]
    articles: list[dict[str, Any]]
    chunks: list[dict[str, Any]]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_rows(tables: CorpusTables) -> None:
    problems: list[str] = []
    doc_keys = {(row["doc_id"], row["lang"]) for row in tables.documents}
    article_ids = set()
    for row in tables.documents:
        if row["lang"] not in LANGS:
            problems.append(f"bad document lang: {row['lang']!r}")
        if row["doc_type"] not in DOC_TYPES:
            problems.append(f"bad doc_type: {row['doc_type']!r}")
        if row["status"] not in DOC_STATUSES:
            problems.append(f"bad document status: {row['status']!r}")
    for row in tables.articles:
        article_ids.add(row["article_id"])
        expected = f"{row['doc_id']}:{row['lang']}:{row['unit_key']}"
        if row["article_id"] != expected:
            problems.append(f"{row['article_id']}: expected id {expected}")
        if (row["doc_id"], row["lang"]) not in doc_keys:
            problems.append(f"{row['article_id']}: missing document")
        if row["unit_type"] not in UNIT_TYPES:
            problems.append(f"{row['article_id']}: bad unit_type")
        if row["unit_status"] not in UNIT_STATUSES:
            problems.append(f"{row['article_id']}: bad unit_status")
        if not UNIT_KEY_RE.match(row["unit_key"]):
            problems.append(f"{row['article_id']}: bad unit_key")
        if row["has_amendments"] != bool(row["amendment_notes"]):
            problems.append(f"{row['article_id']}: amendment flag mismatch")
    for row in tables.chunks:
        if row["article_id"] not in article_ids:
            problems.append(f"{row['chunk_id']}: missing article")
        if row["chunk_id"] != f"{row['article_id']}:c{row['chunk_index']}":
            problems.append(f"{row['chunk_id']}: bad chunk id")
        if not row["text_for_embedding"].strip():
            problems.append(f"{row['chunk_id']}: empty embedding text")
    if problems:
        raise SchemaError("; ".join(problems[:20]))


def write_parquet_dataset(tables: CorpusTables, out_dir: Path) -> dict[str, Any]:
    validate_rows(tables)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "documents.parquet": (tables.documents, DOCUMENT_SCHEMA),
        "articles.parquet": (tables.articles, ARTICLE_SCHEMA),
        "chunks.parquet": (tables.chunks, CHUNK_SCHEMA),
    }
    manifest: dict[str, Any] = {"row_counts": {}, "sha256": {}}
    for filename, (rows, schema) in outputs.items():
        path = out_dir / filename
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
        manifest["row_counts"][filename.removesuffix(".parquet")] = len(rows)
        manifest["sha256"][filename] = file_sha256(path)
    return manifest


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
