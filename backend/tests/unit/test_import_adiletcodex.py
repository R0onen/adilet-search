"""dev/import_adiletcodex.py: AdiletCodex rows -> data_schema.md Parquet (tiny synthetic CSV)."""

import csv
import gzip
from pathlib import Path

import pytest

from dev.import_adiletcodex import chunk_paragraphs, convert, read_rows, split_notes, write
from indexer.corpus import load_corpus

FIELDS = [
    "doc_id", "doc_type", "slug", "lang", "title", "status", "doc_date", "doc_number", "act_form",
    "legal_sphere", "legal_force", "adopting_organ", "database_section", "state_registry_number",
    "npa_registration_number", "adoption_date", "change_date", "publication_date",
    "adoption_place", "region_action", "part", "section", "chapter", "article_id", "article_no",
    "article_title", "article_text", "url",
]  # fmt: skip

LONG = "\n".join(f"{i}. " + "Слово " * 60 for i in range(1, 8))  # ~3 000 chars


def row(
    lang: str, no: str, anchor: str, title: str, text: str, doc: str = "K030000442_"
) -> dict[str, str]:
    base = {f: "" for f in FIELDS}
    lang_dir = {"rus": "rus", "kaz": "kaz", "eng": "eng"}[lang]
    base.update(
        doc_id=doc,
        doc_type="code",
        lang=lang,
        title={
            "rus": "Земельный кодекс Республики Казахстан",
            "kaz": "Қазақстан Республикасының Жер кодексі",
            "eng": "Land Code",
        }[lang],
        status={"rus": "Обновленный", "kaz": "Жаңартылған", "eng": "Updated"}[lang],
        doc_date="2003-06-20",
        doc_number="442",
        adoption_date="20.06.2003",
        change_date="08.09.2026",
        chapter="Глава 1",
        article_id=anchor,
        article_no=no,
        article_title=title,
        article_text=text,
        url=f"https://old.adilet.zan.kz/{lang_dir}/docs/{doc}",
    )
    return base


ROWS = [
    row(
        "rus",
        "1",
        "z1",
        "Статья 1. Земельный фонд",
        "Сноска. Статья 1 с изменениями от 2020.\n"
        "Земельный фонд делится на категории.\nВторой абзац.",
    ),
    row(
        "kaz",
        "1",
        "z1",
        "1-бап. Жер қоры",
        "Ескерту. 1-бапқа өзгеріс енгізілді.\nЖер қоры санаттарға бөлінеді.",
    ),
    row("eng", "1", "z1", "Article 1. Land fund", "The land fund is divided."),
    row("rus", "2", "z2", "Статья 2. Исключена", "Исключена Законом РК от 01.01.2020 № 1-VI."),
    row(
        "rus",
        "3",
        "z3",
        "Статья 3. Частично",
        "Исключен Законом РК от 01.04.2019.\nЧасть вторая остаётся в силе.",
    ),
    row("rus", "3", "z300", "Статья 3. Повтор", "Дубликат номера статьи."),
    row("rus", "4", "z4", "Статья 4. Длинная", LONG),
]


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "adiletcodex.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(ROWS)
    return path


def test_converted_corpus_is_schema_valid(csv_path: Path, tmp_path: Path) -> None:
    documents, articles, chunks = convert(read_rows(csv_path), acts=None)
    out = tmp_path / "processed"
    write(out, documents, articles, chunks)
    corpus = load_corpus(out)  # the indexer's strict validator
    assert {(d["doc_id"], d["lang"]) for d in corpus.documents} == {
        ("K030000442_", "ru"),
        ("K030000442_", "kk"),
    }  # English is not part of the product
    assert all(d["status"] == "in_force" for d in corpus.documents)
    assert corpus.corpus_version == "2026.09.17"


def test_footnotes_move_to_amendment_notes_and_text_stays_verbatim(csv_path: Path) -> None:
    _, articles, _ = convert(read_rows(csv_path), acts=None)
    first = next(a for a in articles if a["article_id"] == "K030000442_:ru:a1")
    assert first["text"] == "Земельный фонд делится на категории.\nВторой абзац."
    assert first["amendment_notes"] == ["Сноска. Статья 1 с изменениями от 2020."]
    assert first["has_amendments"] is True
    assert first["unit_title"] == "Земельный фонд"
    assert first["source_url"] == "https://old.adilet.zan.kz/rus/docs/K030000442_#z1"
    assert first["parallel_article_id"] == "K030000442_:kk:a1"


def test_only_whole_article_exclusions_are_excluded(csv_path: Path) -> None:
    _, articles, _ = convert(read_rows(csv_path), acts=None)
    status = {a["article_id"]: a["unit_status"] for a in articles}
    assert status["K030000442_:ru:a2"] == "excluded"
    assert status["K030000442_:ru:a3"] == "in_force"  # one part repealed, the rest in force


def test_duplicate_article_numbers_get_unique_keys(csv_path: Path) -> None:
    _, articles, _ = convert(read_rows(csv_path), acts=None)
    keys = [a["unit_key"] for a in articles if a["lang"] == "ru"]
    assert "a3" in keys
    assert "a3-z300" in keys
    assert len(keys) == len(set(keys))


def test_long_articles_are_chunked_with_overlap(csv_path: Path) -> None:
    _, _, chunks = convert(read_rows(csv_path), acts=None)
    long_chunks = [c for c in chunks if c["article_id"] == "K030000442_:ru:a4"]
    assert len(long_chunks) >= 2
    assert all(len(c["text"]) <= 1500 for c in long_chunks)
    first_last = long_chunks[0]["text"].split("\n")[-1]
    assert long_chunks[1]["text"].startswith(first_last)  # one paragraph of overlap
    assert long_chunks[0]["text_for_embedding"].startswith(
        "Земельный кодекс РК. Статья 4. Длинная\n"
    )


def test_kazakh_header_and_short_title(csv_path: Path) -> None:
    _, _, chunks = convert(read_rows(csv_path), acts=None)
    kk = next(c for c in chunks if c["article_id"] == "K030000442_:kk:a1")
    assert kk["text_for_embedding"].startswith("ҚР Жер кодексі. 1-бап. Жер қоры\n")


def test_tier1_filter_uses_corpus_config(csv_path: Path) -> None:
    acts = {"K030000442_": {"short_title_ru": "ЗК РК", "short_title_kk": "ҚР ЖК"}}
    documents, _, _ = convert(read_rows(csv_path), acts=acts)
    assert {d["short_title"] for d in documents} == {"ЗК РК", "ҚР ЖК"}
    assert convert(read_rows(csv_path), acts={"OTHER": {}})[0] == []


def test_split_notes_and_chunker_edges() -> None:
    assert split_notes("Текст") == ("Текст", [])
    assert chunk_paragraphs("короткий") == ["короткий"]
    huge = "слово " * 1000
    parts = chunk_paragraphs(huge)
    assert all(len(p) <= 1500 for p in parts)
    assert "".join(parts).replace(" ", "") == huge.replace(" ", "")
