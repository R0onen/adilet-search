"""Convert the public AdiletCodex corpus into the contracts/data_schema.md Parquet files.

    python -m dev.import_adiletcodex --csv data/raw/adiletcodex/adiletcodex.csv.gz \
        --out data/processed [--corpus-config ../ml/configs/corpus.yaml] [--all-acts]

AdiletCodex v1.0 (Mukhsimbayev, Pak, Kuralbayev; CC-BY-4.0; https://zenodo.org/records/22812626)
is an article-level corpus of the in-force codes and laws of Kazakhstan parsed from
adilet.zan.kz, in Kazakh, Russian and English. This bridge gives the project a real corpus until
ML's own scraper (ML-01) ships; ML may adopt or replace it.

- Only `ru` and `kk` are kept (ISO 639-1; the English rows are not part of the product).
- By default only the Tier-1 acts of `ml/configs/corpus.yaml` are converted (PROJECT_PLAN §6);
  `--all-acts` converts every document.
- Statute text is kept verbatim: NFC normalisation and trimming only. The «Сноска.» / «Ескерту.»
  amendment lines move from the text to `amendment_notes`, as data_schema.md §4 requires.
- Articles are chunked by paragraphs (about 400 tokens, one paragraph of overlap), each chunk
  with the header «{short_title}. Статья {N}. {title}» / «{short_title}. {N}-бап. {title}».
"""

import argparse
import csv
import gzip
import hashlib
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from dev.sample_corpus import ARTICLE_SCHEMA, CHUNK_SCHEMA, DOCUMENT_SCHEMA

LANGS = {"rus": "ru", "kaz": "kk"}
# The dataset's publication date on Zenodo stands in for the scrape date.
SCRAPED_AT = datetime(2026, 9, 17, tzinfo=UTC)
CORPUS_VERSION = "2026.09.17"
# ~400 E5 tokens: Russian/Kazakh legal text averages ~3.8 characters per token.
MAX_CHUNK_CHARS = 1500
CHARS_PER_TOKEN = 3.8

REPEALED_STATUSES = {"Күшін жойған", "Invalidated", "Утративший силу", "Утратил силу"}
NOTE_RE = re.compile(r"^\s*(Сноска|Ескерту)\s*\.", re.IGNORECASE)
TITLE_PREFIX_RE = re.compile(r"^\s*(Статья\s+[\w\-]+\.?|[\w\-]+\s*-\s*бап\.?)\s*", re.IGNORECASE)
# A whole article is excluded only when its entire body is the exclusion notice. Texts that start
# with «Исключен…» and go on are partial exclusions (one part repealed, the rest in force).
EXCLUDED_RE = re.compile(
    r"^\s*(Исключена|Исключен|Утратила силу|Утратил силу|Алып\s+тасталды|Күші\s+жойылды)\b",
    re.IGNORECASE,
)
UNIT_KEY_SAFE = re.compile(r"[^a-z0-9-]+")


def nfc(text: str | None) -> str:
    return unicodedata.normalize("NFC", (text or "").replace("\r\n", "\n")).strip()


def parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def short_title(title: str, lang: str) -> str:
    """Fallback short title for acts outside corpus.yaml."""
    if lang == "ru":
        return re.sub(r"\s+Республики Казахстан\b", " РК", title).strip()
    return re.sub(r"^Қазақстан Республикасының\s+", "ҚР ", title, flags=re.IGNORECASE).strip()


def split_notes(text: str) -> tuple[str, list[str]]:
    """Move whole «Сноска. …» / «Ескерту. …» lines out of the article text."""
    body: list[str] = []
    notes: list[str] = []
    for line in text.split("\n"):
        (notes if NOTE_RE.match(line) else body).append(line)
    return "\n".join(body).strip(), [n.strip() for n in notes if n.strip()]


def unit_title(article_title: str) -> str | None:
    title = TITLE_PREFIX_RE.sub("", nfc(article_title)).strip()
    return title or None


def chunk_paragraphs(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Paragraph chunks of at most ~limit chars; neighbours overlap by one paragraph."""
    paragraphs = [p for p in text.split("\n") if p.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:  # hard-split paragraphs that alone exceed the limit
        while len(paragraph) > limit:
            cut = paragraph.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            pieces.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if paragraph:
            pieces.append(paragraph)
    if not pieces:
        return [text]
    chunks: list[str] = []
    current = [pieces[0]]
    for piece in pieces[1:]:
        if sum(len(p) + 1 for p in current) + len(piece) > limit:
            chunks.append("\n".join(current))
            current = [current[-1], piece] if len(current[-1]) + len(piece) < limit else [piece]
        else:
            current.append(piece)
    chunks.append("\n".join(current))
    return chunks


def header(short: str, number: str | None, title: str | None, lang: str) -> str:
    parts = [short]
    if number:
        parts.append(f"Статья {number}" if lang == "ru" else f"{number}-бап")
    if title:
        parts.append(title)
    return ". ".join(parts)


def load_tier1(config_path: Path) -> dict[str, dict[str, Any]]:
    import yaml

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {act["doc_id"]: act for act in config["acts"]}


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize if sys.maxsize < 2**31 else 2**31 - 1)
    with gzip.open(csv_path, "rt", encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["lang"] in LANGS]


def convert(
    rows: list[dict[str, str]], acts: dict[str, dict[str, Any]] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if acts is not None:
        rows = [r for r in rows if r["doc_id"] in acts]
    by_doc: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_doc[(row["doc_id"], LANGS[row["lang"]])].append(row)

    documents: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    for (doc_id, lang), doc_rows in sorted(by_doc.items()):
        first = doc_rows[0]
        title = nfc(first["title"])
        act = (acts or {}).get(doc_id)
        short = act[f"short_title_{lang}"] if act else short_title(title, lang)
        statuses = {nfc(r["status"]) for r in doc_rows}
        documents.append(
            {
                "doc_id": doc_id,
                "lang": lang,
                "title": title,
                "short_title": short,
                "doc_type": first["doc_type"] if first["doc_type"] in ("code", "law") else "other",
                "number": nfc(first["doc_number"]) or None,
                "adopted_date": parse_date(first["adoption_date"]) or parse_date(first["doc_date"]),
                "revision_date": parse_date(first["change_date"]),
                "status": "repealed" if statuses & REPEALED_STATUSES else "in_force",
                "source_url": nfc(first["url"]),
                "article_count": len(doc_rows),
                "scraped_at": SCRAPED_AT,
                "corpus_version": CORPUS_VERSION,
            }
        )
        seen_keys: set[str] = set()
        for order, row in enumerate(doc_rows):
            number = nfc(row["article_no"]) or None
            base = UNIT_KEY_SAFE.sub("-", f"a{(number or row['article_id']).lower()}").strip("-")
            key = base
            if key in seen_keys:  # 11 rows reuse an article number: add adilet's anchor id
                key = UNIT_KEY_SAFE.sub("-", f"{base}-{row['article_id'].lower()}").strip("-")
            seen_keys.add(key)
            text, notes = split_notes(nfc(row["article_text"]))
            text = text or nfc(row["article_title"])
            excluded = len(text.splitlines()) == 1 and bool(EXCLUDED_RE.match(text))
            articles.append(
                {
                    "article_id": f"{doc_id}:{lang}:{key}",
                    "doc_id": doc_id,
                    "lang": lang,
                    "unit_type": "article",
                    "unit_key": key,
                    "unit_number": number,
                    "unit_title": unit_title(row["article_title"]),
                    "unit_order": order,
                    "unit_status": "excluded" if excluded else "in_force",
                    "section_title": nfc(row["section"]) or nfc(row["part"]) or None,
                    "chapter_title": nfc(row["chapter"]) or None,
                    "has_amendments": bool(notes),
                    "source_url": f"{nfc(row['url'])}#{row['article_id']}",
                    "parallel_article_id": None,
                    "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "text": text,
                    "amendment_notes": notes,
                    "_short": short,
                    "_doc": documents[-1],
                }
            )

    ids = {a["article_id"] for a in articles}
    for article in articles:
        other = "kk" if article["lang"] == "ru" else "ru"
        parallel = f"{article['doc_id']}:{other}:{article['unit_key']}"
        article["parallel_article_id"] = parallel if parallel in ids else None

    chunks: list[dict[str, Any]] = []
    for article in articles:
        doc = article.pop("_doc")
        short = article.pop("_short")
        parts = chunk_paragraphs(article["text"])
        head = header(short, article["unit_number"], article["unit_title"], article["lang"])
        shared = {k: v for k, v in article.items() if k not in ("text", "amendment_notes")}
        for index, part in enumerate(parts):
            chunks.append(
                {
                    **shared,
                    "chunk_id": f"{article['article_id']}:c{index}",
                    "chunk_index": index,
                    "chunk_count": len(parts),
                    "text": part,
                    "text_for_embedding": f"{head}\n{part}",
                    "doc_title": doc["title"],
                    "doc_short_title": doc["short_title"],
                    "doc_type": doc["doc_type"],
                    "doc_status": doc["status"],
                    "adopted_date": doc["adopted_date"],
                    "revision_date": doc["revision_date"],
                    "char_len": len(part),
                    "token_len": round(len(part) / CHARS_PER_TOKEN),  # estimate, not tokenizer
                    "chunking_version": "ch1",
                    "corpus_version": CORPUS_VERSION,
                }
            )
    return documents, articles, chunks


def write(out: Path, documents: list[Any], articles: list[Any], chunks: list[Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, rows, schema in (
        ("documents", documents, DOCUMENT_SCHEMA),
        ("articles", articles, ARTICLE_SCHEMA),
        ("chunks", chunks, CHUNK_SCHEMA),
    ):
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), out / f"{name}.parquet")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--corpus-config", type=Path, default=Path("../ml/configs/corpus.yaml"))
    parser.add_argument("--all-acts", action="store_true", help="convert every act, not Tier-1")
    args = parser.parse_args(argv)

    acts = None if args.all_acts else load_tier1(args.corpus_config)
    documents, articles, chunks = convert(read_rows(args.csv), acts)
    write(args.out, documents, articles, chunks)
    excluded = sum(a["unit_status"] == "excluded" for a in articles)
    noted = sum(a["has_amendments"] for a in articles)
    linked = sum(a["parallel_article_id"] is not None for a in articles)
    print(
        f"wrote {len(documents)} documents, {len(articles)} articles ({excluded} excluded, "
        f"{noted} with amendment notes, {linked} RU↔KK linked), {len(chunks)} chunks "
        f"to {args.out} (corpus_version {CORPUS_VERSION})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
