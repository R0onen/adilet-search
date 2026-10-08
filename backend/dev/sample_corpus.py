"""Write a tiny SYNTHETIC corpus in the contracts/data_schema.md Parquet format.

    python -m dev.sample_corpus OUT_DIR

The texts are invented for tests and local development. They are NOT legislation, and every
title says so. Real data comes from the ML agent (`data/sample/`, `data/processed/`). It covers what
the indexer and the search must handle: RU + KK with parallel ids, a long article split into two
chunks, an excluded article, amendment notes, a repealed act, and several document types and dates.
"""

import hashlib
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

CORPUS_VERSION = "2026.10.08-synthetic"
SCRAPED_AT = datetime(2026, 10, 8, tzinfo=UTC)

DOCS: list[dict[str, Any]] = [
    {
        "doc_id": "T0000000001",
        "doc_type": "code",
        "number": "1-T",
        "adopted_date": date(2015, 11, 23),
        "revision_date": date(2026, 1, 1),
        "status": "in_force",
        "ru": ("Тестовый трудовой кодекс (синтетические данные)", "Тестовый ТК"),
        "kk": ("Сынақ еңбек кодексі (синтетикалық деректер)", "Сынақ ЕК"),
    },
    {
        "doc_id": "T0000000002",
        "doc_type": "code",
        "number": "2-T",
        "adopted_date": date(2021, 1, 2),
        "revision_date": date(2025, 6, 1),
        "status": "in_force",
        "ru": ("Тестовый экологический кодекс (синтетические данные)", "Тестовый ЭК"),
        "kk": ("Сынақ экологиялық кодексі (синтетикалық деректер)", "Сынақ ЭК"),
    },
    {
        "doc_id": "T0000000003",
        "doc_type": "law",
        "number": "3-T",
        "adopted_date": date(2001, 5, 10),
        "revision_date": date(2010, 3, 3),
        "status": "repealed",
        "ru": (
            "Тестовый закон о заработной плате (утратил силу, синтетические данные)",
            "Тестовый закон о зарплате",
        ),
        "kk": (
            "Жалақы туралы сынақ заңы (күшін жойған, синтетикалық деректер)",
            "Жалақы туралы сынақ заңы",
        ),
    },
]

# (doc_id, unit_key, number, unit_status, {lang: (title, paragraphs, amendment_notes)})
LONG_RU = [
    "1. За задержку выплаты заработной платы работодатель несёт ответственность, установленную "
    "настоящим тестовым кодексом.",
    "2. При задержке выплаты заработной платы работодатель выплачивает работнику компенсацию за "
    "каждый день задержки.",
    "3. Работник вправе обратиться в инспекцию труда с жалобой на задержку зарплаты.",
    "4. Повторная задержка выплаты заработной платы влечёт штраф для работодателя.",
    "5. Порядок расчёта компенсации определяется уполномоченным органом.",
]
LONG_KK = [
    "1. Жалақыны төлеуді кешіктіргені үшін жұмыс беруші осы сынақ кодексінде белгіленген "
    "жауапкершілікте болады.",
    "2. Жалақыны кешіктірген кезде жұмыс беруші қызметкерге әр күн үшін өтемақы төлейді.",
    "3. Қызметкер жалақының кешіктірілуі туралы еңбек инспекциясына шағым беруге құқылы.",
    "4. Жалақыны қайта кешіктіру жұмыс берушіге айыппұл салуға әкеп соғады.",
    "5. Өтемақыны есептеу тәртібін уәкілетті орган айқындайды.",
]

UNITS: list[tuple[str, str, str, str, dict[str, tuple[str, list[str], list[str]]]]] = [
    (
        "T0000000001",
        "a1",
        "1",
        "in_force",
        {
            "ru": (
                "Сфера действия",
                ["Настоящий тестовый кодекс регулирует трудовые отношения."],
                [],
            ),
            "kk": ("Қолданылу саласы", ["Осы сынақ кодексі еңбек қатынастарын реттейді."], []),
        },
    ),
    (
        "T0000000001",
        "a52",
        "52",
        "in_force",
        {
            "ru": (
                "Основания расторжения трудового договора по инициативе работодателя",
                [
                    "1. Трудовой договор может быть расторгнут по инициативе работодателя в случаях, "
                    "предусмотренных настоящей статьёй.",
                    "2. Основаниями расторжения трудового договора являются ликвидация работодателя и "
                    "сокращение численности работников.",
                ],
                [],
            ),
            "kk": (
                "Еңбек шартын жұмыс берушінің бастамасы бойынша бұзу негіздері",
                [
                    "1. Еңбек шарты осы бапта көзделген жағдайларда жұмыс берушінің бастамасы бойынша "
                    "бұзылуы мүмкін.",
                    "2. Еңбек шартын бұзу негіздері жұмыс берушінің таратылуы және қызметкерлер санының "
                    "қысқаруы болып табылады.",
                ],
                [],
            ),
        },
    ),
    (
        "T0000000001",
        "a53",
        "53",
        "excluded",
        {
            "ru": ("Исключена", ["Статья 53 исключена тестовым изменением."], []),
            "kk": ("Алып тасталды", ["53-бап сынақ өзгерісімен алып тасталды."], []),
        },
    ),
    (
        "T0000000001",
        "a113",
        "113",
        "in_force",
        {
            "ru": (
                "Сроки и порядок выплаты заработной платы",
                [
                    "1. Заработная плата выплачивается работнику не реже одного раза в месяц.",
                    "2. Выплата заработной платы производится в денежной форме.",
                ],
                ["Сноска. Статья 113 с тестовыми изменениями от 01.01.2026."],
            ),
            "kk": (
                "Жалақыны төлеу мерзімдері мен тәртібі",
                [
                    "1. Жалақы қызметкерге айына кемінде бір рет төленеді.",
                    "2. Жалақы ақшалай нысанда төленеді.",
                ],
                ["Ескерту. 113-бапқа 01.01.2026 сынақ өзгерістері енгізілді."],
            ),
        },
    ),
    (
        "T0000000001",
        "a114",
        "114",
        "in_force",
        {
            "ru": (
                "Ответственность работодателя за задержку выплаты заработной платы",
                LONG_RU,
                [],
            ),
            "kk": ("Жалақыны кешіктіргені үшін жұмыс берушінің жауапкершілігі", LONG_KK, []),
        },
    ),
    (
        "T0000000002",
        "a10",
        "10",
        "in_force",
        {
            "ru": (
                "Штрафы за нарушение экологических требований",
                [
                    "1. Нарушение экологических норм при выбросах загрязняющих веществ влечёт штраф.",
                    "2. Размер штрафа за нарушение экологических требований устанавливается в месячных "
                    "расчётных показателях.",
                ],
                [],
            ),
            "kk": (
                "Экологиялық талаптарды бұзғаны үшін айыппұлдар",
                [
                    "1. Ластаушы заттарды шығару кезінде экологиялық нормаларды бұзу айыппұлға әкеп соғады.",
                    "2. Экологиялық талаптарды бұзғаны үшін айыппұл мөлшері айлық есептік көрсеткіштермен "
                    "белгіленеді.",
                ],
                [],
            ),
        },
    ),
    (
        "T0000000003",
        "a5",
        "5",
        "in_force",
        {
            "ru": (
                "Выплата заработной платы",
                ["Заработная плата выплачивалась ежемесячно (утративший силу тестовый текст)."],
                [],
            ),
            "kk": ("Жалақы төлеу", ["Жалақы ай сайын төленді (күшін жойған сынақ мәтіні)."], []),
        },
    ),
]

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
_ARTICLE_FIELDS = [
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
        *_ARTICLE_FIELDS,
        ("text", pa.string()),
        ("amendment_notes", pa.list_(pa.string())),
    ]
)
CHUNK_SCHEMA = pa.schema(
    [
        *_ARTICLE_FIELDS,
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


def _url(doc_id: str, lang: str) -> str:
    return f"https://example.invalid/{'rus' if lang == 'ru' else 'kaz'}/docs/{doc_id}"


def _header(short_title: str, number: str, title: str, lang: str) -> str:
    unit = f"Статья {number}" if lang == "ru" else f"{number}-бап"
    return f"{short_title}. {unit}. {title}"


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    docs = {d["doc_id"]: d for d in DOCS}
    documents, articles, chunks = [], [], []
    for lang in ("ru", "kk"):
        for doc in DOCS:
            title, short = doc[lang]
            units = [u for u in UNITS if u[0] == doc["doc_id"]]
            documents.append(
                {
                    "doc_id": doc["doc_id"],
                    "lang": lang,
                    "title": title,
                    "short_title": short,
                    "doc_type": doc["doc_type"],
                    "number": doc["number"],
                    "adopted_date": doc["adopted_date"],
                    "revision_date": doc["revision_date"],
                    "status": doc["status"],
                    "source_url": _url(doc["doc_id"], lang),
                    "article_count": len(units),
                    "scraped_at": SCRAPED_AT,
                    "corpus_version": CORPUS_VERSION,
                }
            )
        for order, (doc_id, key, number, status, texts) in enumerate(UNITS):
            doc = docs[doc_id]
            title, paragraphs, notes = texts[lang]
            other = "kk" if lang == "ru" else "ru"
            text = "\n".join(paragraphs)
            article = {
                "article_id": f"{doc_id}:{lang}:{key}",
                "doc_id": doc_id,
                "lang": lang,
                "unit_type": "article",
                "unit_key": key,
                "unit_number": number,
                "unit_title": title,
                "unit_order": order,
                "unit_status": status,
                "section_title": None,
                "chapter_title": None,
                "has_amendments": bool(notes),
                "source_url": f"{_url(doc_id, lang)}#a{number}",
                "parallel_article_id": f"{doc_id}:{other}:{key}",
                "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            }
            articles.append({**article, "text": text, "amendment_notes": notes})
            # Long articles become two chunks that overlap by one paragraph (ch1 style).
            parts = [paragraphs] if len(paragraphs) < 5 else [paragraphs[:3], paragraphs[2:]]
            for index, part in enumerate(parts):
                chunk_text = "\n".join(part)
                header = _header(doc[lang][1], number, title, lang)
                chunks.append(
                    {
                        **article,
                        "chunk_id": f"{article['article_id']}:c{index}",
                        "chunk_index": index,
                        "chunk_count": len(parts),
                        "text": chunk_text,
                        "text_for_embedding": f"{header}\n{chunk_text}",
                        "doc_title": doc[lang][0],
                        "doc_short_title": doc[lang][1],
                        "doc_type": doc["doc_type"],
                        "doc_status": doc["status"],
                        "adopted_date": doc["adopted_date"],
                        "revision_date": doc["revision_date"],
                        "char_len": len(chunk_text),
                        "token_len": len(chunk_text.split()),
                        "chunking_version": "ch1",
                        "corpus_version": CORPUS_VERSION,
                    }
                )
    return documents, articles, chunks


def write(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    documents, articles, chunks = build()
    for name, rows, schema in (
        ("documents", documents, DOCUMENT_SCHEMA),
        ("articles", articles, ARTICLE_SCHEMA),
        ("chunks", chunks, CHUNK_SCHEMA),
    ):
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), out_dir / f"{name}.parquet")
    return out_dir


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m dev.sample_corpus OUT_DIR")
    path = write(Path(sys.argv[1]))
    documents, articles, chunks = build()
    print(
        f"wrote {len(documents)} documents, {len(articles)} articles, {len(chunks)} chunks to {path}"
    )
