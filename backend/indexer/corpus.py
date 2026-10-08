"""Load and validate the corpus Parquet files against contracts/data_schema.md §3–5.

Validation fails loudly: every problem found (up to a limit) is listed in one error, so the ML
agent can fix a dataset in one round.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

MAX_REPORTED = 25

LANGS = {"ru", "kk"}
DOC_TYPES = {"code", "law", "decree", "resolution", "order", "other"}
DOC_STATUSES = {"in_force", "repealed", "not_yet_in_force"}
UNIT_TYPES = {"article", "paragraph", "chapter", "preamble", "annex"}
UNIT_STATUSES = {"in_force", "excluded"}

DOC_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")  # real adilet codes end in "_", e.g. K030000442_
UNIT_KEY_RE = re.compile(r"^[a-z0-9-]+$")

# column -> (kind, nullable)
Spec = dict[str, tuple[str, bool]]

DOCUMENTS: Spec = {
    "doc_id": ("string", False),
    "lang": ("string", False),
    "title": ("string", False),
    "short_title": ("string", False),
    "doc_type": ("string", False),
    "number": ("string", True),
    "adopted_date": ("date", True),
    "revision_date": ("date", True),
    "status": ("string", False),
    "source_url": ("string", False),
    "article_count": ("int", False),
    "scraped_at": ("timestamp", False),
    "corpus_version": ("string", False),
}

_ARTICLE_SHARED: Spec = {
    "article_id": ("string", False),
    "doc_id": ("string", False),
    "lang": ("string", False),
    "unit_type": ("string", False),
    "unit_key": ("string", False),
    "unit_number": ("string", True),
    "unit_title": ("string", True),
    "unit_order": ("int", False),
    "unit_status": ("string", False),
    "section_title": ("string", True),
    "chapter_title": ("string", True),
    "has_amendments": ("bool", False),
    "source_url": ("string", False),
    "parallel_article_id": ("string", True),
    "content_hash": ("string", False),
}

ARTICLES: Spec = {
    **_ARTICLE_SHARED,
    "text": ("string", False),
    "amendment_notes": ("list_string", False),
}

CHUNKS: Spec = {
    **_ARTICLE_SHARED,
    "chunk_id": ("string", False),
    "chunk_index": ("int", False),
    "chunk_count": ("int", False),
    "text": ("string", False),
    "text_for_embedding": ("string", False),
    "doc_title": ("string", False),
    "doc_short_title": ("string", False),
    "doc_type": ("string", False),
    "doc_status": ("string", False),
    "adopted_date": ("date", True),
    "revision_date": ("date", True),
    "char_len": ("int", False),
    "token_len": ("int", False),
    "chunking_version": ("string", False),
    "corpus_version": ("string", False),
}

_TYPE_CHECKS: dict[str, Callable[[pa.DataType], bool]] = {
    "string": lambda t: pa.types.is_string(t) or pa.types.is_large_string(t),
    "date": lambda t: pa.types.is_date(t) or pa.types.is_timestamp(t),
    "timestamp": pa.types.is_timestamp,
    "int": pa.types.is_integer,
    "bool": pa.types.is_boolean,
    "list_string": lambda t: (
        (pa.types.is_list(t) or pa.types.is_large_list(t))
        and (pa.types.is_string(t.value_type) or pa.types.is_large_string(t.value_type))
    ),
}


class CorpusError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        shown = problems[:MAX_REPORTED]
        more = f"\n  … and {len(problems) - len(shown)} more" if len(problems) > len(shown) else ""
        super().__init__(
            "corpus does not match contracts/data_schema.md:\n  " + "\n  ".join(shown) + more
        )
        self.problems = problems


@dataclass
class Corpus:
    documents: list[dict[str, Any]]
    articles: list[dict[str, Any]]
    chunks: list[dict[str, Any]]

    @property
    def corpus_version(self) -> str | None:
        versions = {row["corpus_version"] for row in self.documents}
        return versions.pop() if len(versions) == 1 else None


def _check_schema(name: str, schema: pa.Schema, spec: Spec, problems: list[str]) -> None:
    for column, (kind, _) in spec.items():
        if column not in schema.names:
            problems.append(f"{name}: missing column `{column}`")
        elif not _TYPE_CHECKS[kind](schema.field(column).type):
            problems.append(
                f"{name}: column `{column}` has type {schema.field(column).type}, expected {kind}"
            )


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) or value is None else None


def _read(
    path: Path, spec: Spec, structural: list[str], problems: list[str]
) -> list[dict[str, Any]]:
    """Rows of one file. Missing files/columns and wrong types go to `structural`."""
    if not path.exists():
        structural.append(f"missing file {path.name}")
        return []
    table = pq.read_table(path)
    before = len(structural)
    _check_schema(path.name, table.schema, spec, structural)
    if len(structural) > before:
        return []
    rows: list[dict[str, Any]] = table.select(list(spec)).to_pylist()
    for i, row in enumerate(rows):
        for column, (kind, nullable) in spec.items():
            if row[column] is None and not nullable:
                problems.append(f"{path.name} row {i}: `{column}` is null")
            elif kind == "date":
                row[column] = _to_date(row[column])
    return rows


def _enum(problems: list[str], where: str, column: str, value: Any, allowed: set[str]) -> None:
    if value not in allowed:
        problems.append(f"{where}: `{column}`={value!r} not in {sorted(allowed)}")


def validate(corpus: Corpus) -> list[str]:
    problems: list[str] = []
    doc_keys = set()
    for row in corpus.documents:
        where = f"documents {row['doc_id']}/{row['lang']}"
        key = (row["doc_id"], row["lang"])
        if key in doc_keys:
            problems.append(f"{where}: duplicate (doc_id, lang)")
        doc_keys.add(key)
        if not DOC_ID_RE.match(str(row["doc_id"])):
            problems.append(f"{where}: bad doc_id")
        _enum(problems, where, "lang", row["lang"], LANGS)
        _enum(problems, where, "doc_type", row["doc_type"], DOC_TYPES)
        _enum(problems, where, "status", row["status"], DOC_STATUSES)

    article_ids = set()
    for row in corpus.articles:
        where = f"articles {row['article_id']}"
        if row["article_id"] in article_ids:
            problems.append(f"{where}: duplicate article_id")
        article_ids.add(row["article_id"])
        expected = f"{row['doc_id']}:{row['lang']}:{row['unit_key']}"
        if row["article_id"] != expected:
            problems.append(f"{where}: article_id must be {expected!r}")
        if not UNIT_KEY_RE.match(str(row["unit_key"])):
            problems.append(f"{where}: bad unit_key {row['unit_key']!r}")
        if (row["doc_id"], row["lang"]) not in doc_keys:
            problems.append(f"{where}: no document {row['doc_id']}/{row['lang']}")
        _enum(problems, where, "unit_type", row["unit_type"], UNIT_TYPES)
        _enum(problems, where, "unit_status", row["unit_status"], UNIT_STATUSES)
        if row["has_amendments"] != (len(row["amendment_notes"] or []) > 0):
            problems.append(f"{where}: has_amendments disagrees with amendment_notes")

    chunk_ids = set()
    chunked_articles = set()
    for row in corpus.chunks:
        where = f"chunks {row['chunk_id']}"
        if row["chunk_id"] in chunk_ids:
            problems.append(f"{where}: duplicate chunk_id")
        chunk_ids.add(row["chunk_id"])
        expected = f"{row['article_id']}:c{row['chunk_index']}"
        if row["chunk_id"] != expected:
            problems.append(f"{where}: chunk_id must be {expected!r}")
        if row["article_id"] not in article_ids:
            problems.append(f"{where}: no article {row['article_id']}")
        chunked_articles.add(row["article_id"])
        _enum(problems, where, "doc_status", row["doc_status"], DOC_STATUSES)
        _enum(problems, where, "unit_status", row["unit_status"], UNIT_STATUSES)
        _enum(problems, where, "doc_type", row["doc_type"], DOC_TYPES)
        if not str(row["text_for_embedding"]).strip():
            problems.append(f"{where}: empty text_for_embedding")

    missing = article_ids - chunked_articles
    if missing:
        problems.append(f"{len(missing)} articles have no chunks, e.g. {sorted(missing)[:3]}")
    return problems


def load_corpus(data_dir: Path) -> Corpus:
    """Read documents/articles/chunks.parquet from `data_dir` and validate them."""
    structural: list[str] = []
    problems: list[str] = []
    corpus = Corpus(
        documents=_read(data_dir / "documents.parquet", DOCUMENTS, structural, problems),
        articles=_read(data_dir / "articles.parquet", ARTICLES, structural, problems),
        chunks=_read(data_dir / "chunks.parquet", CHUNKS, structural, problems),
    )
    if structural:
        raise CorpusError(structural)
    problems += validate(corpus)
    if problems:
        raise CorpusError(problems)
    return corpus
