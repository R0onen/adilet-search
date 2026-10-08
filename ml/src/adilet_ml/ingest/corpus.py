"""Build contract-shaped corpus tables from Adilet HTML pages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from adilet_ml.chunking.chunker import embedding_header, iter_text_chunks
from adilet_ml.data.schema import CorpusTables, content_hash, write_json, write_parquet_dataset
from adilet_ml.ingest.adilet import adilet_url, fetch_cached, parse_html


@dataclass(frozen=True)
class ActConfig:
    key: str
    doc_id: str
    short_title_ru: str
    short_title_kk: str
    doc_type: str
    tier: int
    languages: list[str]

    def short_title(self, lang: str) -> str:
        return self.short_title_kk if lang == "kk" else self.short_title_ru


def load_corpus_config(path: Path) -> tuple[str, list[ActConfig]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = str(data["corpus_version"])
    acts = [ActConfig(**item) for item in data["acts"]]
    return version, acts


def _unit_key(number: str) -> str:
    return f"a{number}".lower()


def _row_common(act: ActConfig, lang: str, unit_number: str, order: int) -> dict[str, Any]:
    unit_key = _unit_key(unit_number)
    other_lang = "kk" if lang == "ru" else "ru"
    return {
        "article_id": f"{act.doc_id}:{lang}:{unit_key}",
        "doc_id": act.doc_id,
        "lang": lang,
        "unit_type": "article",
        "unit_key": unit_key,
        "unit_number": unit_number,
        "unit_order": order,
        "source_url": f"{adilet_url(act.doc_id, lang)}#z{unit_number}",
        "parallel_article_id": f"{act.doc_id}:{other_lang}:{unit_key}",
    }


def build_from_cached_html(
    *,
    config_path: Path,
    raw_dir: Path,
    out_dir: Path,
    limit_acts: int | None = None,
    max_chunk_tokens: int = 400,
) -> dict[str, Any]:
    corpus_version, acts = load_corpus_config(config_path)
    if limit_acts is not None:
        acts = acts[:limit_acts]
    scraped_at = datetime.now(UTC)
    documents: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []

    for act in acts:
        for lang in act.languages:
            html_path = raw_dir / "adilet" / lang / f"{act.doc_id}.html"
            parsed = parse_html(html_path.read_text(encoding="utf-8"), lang)
            article_count = len(parsed.articles)
            title = parsed.title
            short_title = act.short_title(lang)
            documents.append(
                {
                    "doc_id": act.doc_id,
                    "lang": lang,
                    "title": title,
                    "short_title": short_title,
                    "doc_type": act.doc_type,
                    "number": None,
                    "adopted_date": None,
                    "revision_date": None,
                    "status": "in_force",
                    "source_url": adilet_url(act.doc_id, lang),
                    "article_count": article_count,
                    "scraped_at": scraped_at,
                    "corpus_version": corpus_version,
                }
            )
            for order, item in enumerate(parsed.articles):
                common = _row_common(act, lang, item.unit_number, order)
                article = {
                    **common,
                    "unit_title": item.unit_title,
                    "unit_status": item.unit_status,
                    "section_title": None,
                    "chapter_title": None,
                    "has_amendments": bool(item.amendment_notes),
                    "content_hash": content_hash(item.text),
                    "text": item.text,
                    "amendment_notes": item.amendment_notes,
                }
                articles.append(article)
                meta = dict(article)
                text = meta.pop("text")
                notes = meta.pop("amendment_notes")
                header = embedding_header(short_title, item.unit_number, item.unit_title, lang)
                text_chunks = list(iter_text_chunks(text, max_tokens=max_chunk_tokens))
                for index, chunk_text in enumerate(text_chunks):
                    chunks.append(
                        {
                            **meta,
                            "has_amendments": bool(notes),
                            "chunk_id": f"{article['article_id']}:c{index}",
                            "chunk_index": index,
                            "chunk_count": len(text_chunks),
                            "text": chunk_text,
                            "text_for_embedding": f"{header}\n{chunk_text}",
                            "doc_title": title,
                            "doc_short_title": short_title,
                            "doc_type": act.doc_type,
                            "doc_status": "in_force",
                            "adopted_date": None,
                            "revision_date": None,
                            "char_len": len(chunk_text),
                            "token_len": len(chunk_text.split()),
                            "chunking_version": "ch1",
                            "corpus_version": corpus_version,
                        }
                    )

    tables = CorpusTables(documents=documents, articles=articles, chunks=chunks)
    manifest = write_parquet_dataset(tables, out_dir)
    manifest.update(
        {
            "corpus_version": corpus_version,
            "scraped_at": scraped_at.isoformat(),
            "source": "cached_adilet_html",
        }
    )
    write_json(out_dir.parent / "MANIFEST.json", manifest)
    return manifest


def fetch_target_html(
    config_path: Path,
    raw_dir: Path,
    limit_acts: int | None = None,
) -> list[Path]:
    _, acts = load_corpus_config(config_path)
    if limit_acts is not None:
        acts = acts[:limit_acts]
    paths: list[Path] = []
    for act in acts:
        for lang in act.languages:
            paths.append(fetch_cached(act.doc_id, lang, raw_dir / "adilet"))
    return paths


def config_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
