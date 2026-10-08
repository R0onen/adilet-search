"""Build the committed bootstrap sample in `contracts/data_schema.md` format."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from adilet_ml.chunking.chunker import embedding_header, iter_text_chunks

CORPUS_VERSION = "2026.10.08-bootstrap"
SCRAPED_AT = datetime(2026, 10, 8, tzinfo=UTC)
DOC_ID = "K1500000414"
DOC_NUMBER = "414-V"
DOC_DATE = date(2015, 11, 23)
REVISION_DATE = date(2026, 7, 1)

DOC_TITLES = {
    "ru": (
        "Трудовой кодекс Республики Казахстан (bootstrap sample)",
        "Трудовой кодекс РК",
    ),
    "kk": (
        "Қазақстан Республикасының Еңбек кодексі (bootstrap sample)",
        "ҚР Еңбек кодексі",
    ),
}

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

UNIT_DATA: list[dict[str, Any]] = [
    {
        "number": "1",
        "section_ru": "Раздел 1. Общие положения",
        "chapter_ru": "Глава 1. Основные положения",
        "section_kk": "1-бөлім. Жалпы ережелер",
        "chapter_kk": "1-тарау. Негізгі ережелер",
        "ru_title": "Основные понятия, используемые в настоящем Кодексе",
        "kk_title": "Осы Кодексте пайдаланылатын негізгі ұғымдар",
        "ru": [
            "В учебном фрагменте перечисляются основные термины трудового права: работник, работодатель, трудовой договор, рабочее время и время отдыха.",
            "Этот материал нужен только для интеграционного тестирования поиска и не заменяет официальный текст закона.",
        ],
        "kk": [
            "Оқу үзіндісінде еңбек құқығының негізгі ұғымдары көрсетіледі: қызметкер, жұмыс беруші, еңбек шарты, жұмыс уақыты және тынығу уақыты.",
            "Бұл материал іздеуді интеграциялық тексеруге ғана арналған және ресми заң мәтінін алмастырмайды.",
        ],
    },
    {
        "number": "2",
        "ru_title": "Трудовое законодательство Республики Казахстан",
        "kk_title": "Қазақстан Республикасының еңбек заңнамасы",
        "ru": [
            "Трудовое законодательство определяет права и обязанности сторон трудовых отношений и общие гарантии их защиты.",
            "Если международным договором установлены иные правила, приоритет определяется законодательством Республики Казахстан.",
        ],
        "kk": [
            "Еңбек заңнамасы еңбек қатынастары тараптарының құқықтары мен міндеттерін және оларды қорғаудың жалпы кепілдіктерін айқындайды.",
            "Халықаралық шартта өзге қағидалар белгіленсе, басымдық Қазақстан Республикасының заңнамасына сәйкес анықталады.",
        ],
    },
    {
        "number": "23",
        "ru_title": "Основные права и обязанности работника",
        "kk_title": "Қызметкердің негізгі құқықтары мен міндеттері",
        "ru": [
            "Работник вправе получать заработную плату своевременно и в полном размере, а также требовать безопасных условий труда.",
            "Работник обязан добросовестно выполнять трудовые обязанности и соблюдать трудовую дисциплину.",
        ],
        "kk": [
            "Қызметкер жалақыны уақтылы және толық мөлшерде алуға, сондай-ақ қауіпсіз еңбек жағдайларын талап етуге құқылы.",
            "Қызметкер еңбек міндеттерін адал орындауға және еңбек тәртібін сақтауға міндетті.",
        ],
    },
    {
        "number": "30",
        "ru_title": "Срок трудового договора",
        "kk_title": "Еңбек шартының мерзімі",
        "ru": [
            "Трудовой договор может заключаться на неопределенный срок либо на определенный срок в случаях, предусмотренных законом.",
            "Условие о сроке должно быть ясно отражено в договоре и понятно обеим сторонам.",
        ],
        "kk": [
            "Еңбек шарты белгісіз мерзімге немесе заңда көзделген жағдайларда белгілі бір мерзімге жасалуы мүмкін.",
            "Мерзім туралы талап шартта анық көрсетіліп, екі тарапқа да түсінікті болуға тиіс.",
        ],
    },
    {
        "number": "33",
        "ru_title": "Документы, необходимые для заключения трудового договора",
        "kk_title": "Еңбек шартын жасасу үшін қажетті құжаттар",
        "ru": [
            "При заключении трудового договора работодатель запрашивает документы, подтверждающие личность, образование и квалификацию работника.",
            "Запрос иных документов допускается только когда это прямо предусмотрено законодательством.",
        ],
        "kk": [
            "Еңбек шартын жасасу кезінде жұмыс беруші қызметкердің жеке басын, білімін және біліктілігін растайтын құжаттарды сұратады.",
            "Өзге құжаттарды сұратуға заңнамада тікелей көзделген кезде ғана жол беріледі.",
        ],
    },
    {
        "number": "52",
        "ru_title": "Основания расторжения трудового договора по инициативе работодателя",
        "kk_title": "Еңбек шартын жұмыс берушінің бастамасы бойынша бұзу негіздері",
        "ru": [
            "Трудовой договор может быть расторгнут по инициативе работодателя при ликвидации работодателя, сокращении численности работников или нарушении работником трудовых обязанностей.",
            "Работодатель обязан соблюдать порядок уведомления и гарантии, предусмотренные трудовым законодательством.",
        ],
        "kk": [
            "Еңбек шарты жұмыс берушінің бастамасы бойынша жұмыс беруші таратылғанда, қызметкерлер саны қысқарғанда немесе қызметкер еңбек міндеттерін бұзғанда бұзылуы мүмкін.",
            "Жұмыс беруші еңбек заңнамасында көзделген хабарлау тәртібі мен кепілдіктерді сақтауға міндетті.",
        ],
    },
    {
        "number": "53",
        "status": "excluded",
        "ru_title": "Исключена",
        "kk_title": "Алып тасталды",
        "ru": ["Статья 53 исключена из bootstrap sample, чтобы проверить фильтрацию недействующих норм."],
        "kk": ["53-бап bootstrap sample ішінен алып тасталған бап ретінде берілді, бұл қолданыста жоқ нормаларды сүзуді тексеру үшін қажет."],
    },
    {
        "number": "65",
        "ru_title": "Режим рабочего времени",
        "kk_title": "Жұмыс уақытының режимі",
        "ru": [
            "Режим рабочего времени устанавливает продолжительность рабочей недели, начало и окончание рабочего дня, перерывы и сменность.",
            "Работодатель знакомит работников с режимом рабочего времени до начала работы.",
        ],
        "kk": [
            "Жұмыс уақытының режимі жұмыс аптасының ұзақтығын, жұмыс күнінің басталуы мен аяқталуын, үзілістер мен ауысымдылықты белгілейді.",
            "Жұмыс беруші қызметкерлерді жұмыс басталғанға дейін жұмыс уақытының режимімен таныстырады.",
        ],
    },
    {
        "number": "77",
        "ru_title": "Оплата сверхурочной работы",
        "kk_title": "Үстеме жұмысқа ақы төлеу",
        "ru": [
            "Сверхурочная работа оплачивается в повышенном размере либо компенсируется временем отдыха, если это допускается соглашением сторон.",
            "Привлечение к сверхурочной работе требует учета ограничений и письменного согласия в предусмотренных случаях.",
        ],
        "kk": [
            "Үстеме жұмысқа жоғарылатылған мөлшерде ақы төленеді немесе тараптардың келісімімен тынығу уақытымен өтеледі.",
            "Үстеме жұмысқа тарту шектеулерді есепке алуды және көзделген жағдайларда жазбаша келісімді талап етеді.",
        ],
    },
    {
        "number": "87",
        "ru_title": "Ежегодный оплачиваемый трудовой отпуск",
        "kk_title": "Жыл сайынғы ақы төленетін еңбек демалысы",
        "ru": [
            "Работнику предоставляется ежегодный оплачиваемый трудовой отпуск с сохранением места работы и средней заработной платы.",
            "График отпусков утверждается работодателем с учетом мнения работников и производственной необходимости.",
        ],
        "kk": [
            "Қызметкерге жұмыс орны мен орташа жалақысы сақтала отырып жыл сайынғы ақы төленетін еңбек демалысы беріледі.",
            "Демалыс кестесін жұмыс беруші қызметкерлердің пікірін және өндірістік қажеттілікті ескере отырып бекітеді.",
        ],
    },
    {
        "number": "96",
        "ru_title": "Дисциплинарное взыскание",
        "kk_title": "Тәртіптік жаза",
        "ru": [
            "За дисциплинарный проступок работодатель вправе применить замечание, выговор или расторжение трудового договора по соответствующим основаниям.",
            "До применения взыскания у работника запрашивается письменное объяснение.",
        ],
        "kk": [
            "Тәртіптік теріс қылық үшін жұмыс беруші ескерту, сөгіс немесе тиісті негіздер бойынша еңбек шартын бұзуды қолдануға құқылы.",
            "Жаза қолданылғанға дейін қызметкерден жазбаша түсініктеме сұратылады.",
        ],
    },
    {
        "number": "107",
        "ru_title": "Минимальный размер заработной платы",
        "kk_title": "Жалақының ең төмен мөлшері",
        "ru": [
            "Месячная заработная плата работника не может быть ниже минимального размера заработной платы при выполнении нормы рабочего времени.",
            "Иные выплаты и компенсации начисляются с учетом условий трудового договора и законодательства.",
        ],
        "kk": [
            "Қызметкердің айлық жалақысы жұмыс уақытының нормасын орындаған кезде жалақының ең төмен мөлшерінен төмен болмауға тиіс.",
            "Өзге төлемдер мен өтемақылар еңбек шартының талаптары және заңнама ескеріле отырып есептеледі.",
        ],
    },
    {
        "number": "113",
        "notes_ru": ["Сноска. В bootstrap sample статья 113 помечена как измененная для проверки amendment_notes."],
        "notes_kk": ["Ескерту. Bootstrap sample ішінде 113-бап amendment_notes тексеру үшін өзгертілген деп белгіленді."],
        "ru_title": "Сроки и порядок выплаты заработной платы",
        "kk_title": "Жалақыны төлеу мерзімдері мен тәртібі",
        "ru": [
            "Заработная плата выплачивается работнику не реже одного раза в месяц в день, установленный трудовым договором или актом работодателя.",
            "При совпадении дня выплаты с выходным или праздничным днем выплата производится накануне такого дня.",
        ],
        "kk": [
            "Жалақы қызметкерге еңбек шартында немесе жұмыс берушінің актісінде белгіленген күні айына кемінде бір рет төленеді.",
            "Төлем күні демалыс немесе мереке күніне сәйкес келсе, төлем сол күннің қарсаңында жүргізіледі.",
        ],
    },
    {
        "number": "114",
        "ru_title": "Ответственность работодателя за задержку выплаты заработной платы",
        "kk_title": "Жалақыны төлеуді кешіктіргені үшін жұмыс берушінің жауапкершілігі",
        "ru": [
            "За задержку выплаты заработной платы работодатель несет ответственность и обязан выплатить работнику задолженность.",
            "Компенсация начисляется за каждый день задержки, если задержка возникла по вине работодателя.",
            "Работник вправе обратиться в государственную инспекцию труда с жалобой на нарушение сроков выплаты.",
            "Повторное нарушение порядка выплаты заработной платы учитывается при оценке ответственности работодателя.",
            "Порядок расчета компенсации и сроки перечисления фиксируются в документах работодателя.",
            "Этот длинный учебный фрагмент намеренно разбит на несколько абзацев, чтобы проверить chunking_version ch1 и перекрытие соседних чанков.",
        ],
        "kk": [
            "Жалақыны төлеуді кешіктіргені үшін жұмыс беруші жауапты болады және қызметкерге берешекті төлеуге міндетті.",
            "Егер кешіктіру жұмыс берушінің кінәсінен туындаса, өтемақы әрбір кешіктірілген күн үшін есептеледі.",
            "Қызметкер төлем мерзімдерінің бұзылуы туралы мемлекеттік еңбек инспекциясына шағым беруге құқылы.",
            "Жалақыны төлеу тәртібін қайталап бұзу жұмыс берушінің жауапкершілігін бағалау кезінде ескеріледі.",
            "Өтемақыны есептеу тәртібі мен аудару мерзімдері жұмыс берушінің құжаттарында бекітіледі.",
            "Бұл ұзын оқу үзіндісі ch1 chunking_version және көршілес чанктардың қабаттасуын тексеру үшін бірнеше абзацқа бөлінді.",
        ],
    },
    {
        "number": "115",
        "ru_title": "Гарантии при удержаниях из заработной платы",
        "kk_title": "Жалақыдан ұстап қалу кезіндегі кепілдіктер",
        "ru": [
            "Удержания из заработной платы допускаются в случаях, предусмотренных законом, судебным актом или письменным согласием работника.",
            "Размер удержаний не должен лишать работника гарантированной части заработной платы.",
        ],
        "kk": [
            "Жалақыдан ұстап қалуға заңда, сот актісінде немесе қызметкердің жазбаша келісімінде көзделген жағдайларда жол беріледі.",
            "Ұстап қалу мөлшері қызметкерді жалақының кепілдік берілген бөлігінен айырмауға тиіс.",
        ],
    },
]


def source_url(lang: str, number: str | None = None) -> str:
    prefix = "rus" if lang == "ru" else "kaz"
    base = f"https://adilet.zan.kz/{prefix}/docs/{DOC_ID}"
    return f"{base}#a{number}" if number else base


def _article_row(unit: dict[str, Any], lang: str, order: int) -> dict[str, Any]:
    number = unit["number"]
    unit_key = f"a{number}"
    text = "\n".join(unit[lang])
    other = "kk" if lang == "ru" else "ru"
    return {
        "article_id": f"{DOC_ID}:{lang}:{unit_key}",
        "doc_id": DOC_ID,
        "lang": lang,
        "unit_type": "article",
        "unit_key": unit_key,
        "unit_number": number,
        "unit_title": unit[f"{lang}_title"],
        "unit_order": order,
        "unit_status": unit.get("status", "in_force"),
        "section_title": unit.get(f"section_{lang}"),
        "chapter_title": unit.get(f"chapter_{lang}"),
        "has_amendments": bool(unit.get(f"notes_{lang}", [])),
        "source_url": source_url(lang, number),
        "parallel_article_id": f"{DOC_ID}:{other}:{unit_key}",
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "amendment_notes": unit.get(f"notes_{lang}", []),
    }


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for lang in ("ru", "kk"):
        title, short_title = DOC_TITLES[lang]
        documents.append(
            {
                "doc_id": DOC_ID,
                "lang": lang,
                "title": title,
                "short_title": short_title,
                "doc_type": "code",
                "number": DOC_NUMBER,
                "adopted_date": DOC_DATE,
                "revision_date": REVISION_DATE,
                "status": "in_force",
                "source_url": source_url(lang),
                "article_count": len(UNIT_DATA),
                "scraped_at": SCRAPED_AT,
                "corpus_version": CORPUS_VERSION,
            }
        )
        for order, unit in enumerate(UNIT_DATA):
            article = _article_row(unit, lang, order)
            articles.append(dict(article))
            article_meta = dict(article)
            text = article_meta.pop("text")
            notes = article_meta.pop("amendment_notes")
            text_chunks = list(iter_text_chunks(text, max_tokens=48))
            header = embedding_header(short_title, unit["number"], unit[f"{lang}_title"], lang)
            for index, chunk_text in enumerate(text_chunks):
                chunks.append(
                    {
                        **article_meta,
                        "has_amendments": bool(notes),
                        "chunk_id": f"{article['article_id']}:c{index}",
                        "chunk_index": index,
                        "chunk_count": len(text_chunks),
                        "text": chunk_text,
                        "text_for_embedding": f"{header}\n{chunk_text}",
                        "doc_title": title,
                        "doc_short_title": short_title,
                        "doc_type": "code",
                        "doc_status": "in_force",
                        "adopted_date": DOC_DATE,
                        "revision_date": REVISION_DATE,
                        "char_len": len(chunk_text),
                        "token_len": len(chunk_text.split()),
                        "chunking_version": "ch1",
                        "corpus_version": CORPUS_VERSION,
                    }
                )
    return documents, articles, chunks


def write(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    documents, articles, chunks = build()
    outputs = {
        "documents.parquet": (documents, DOCUMENT_SCHEMA),
        "articles.parquet": (articles, ARTICLE_SCHEMA),
        "chunks.parquet": (chunks, CHUNK_SCHEMA),
    }
    manifest: dict[str, Any] = {
        "corpus_version": CORPUS_VERSION,
        "scraped_at": SCRAPED_AT.isoformat(),
        "row_counts": {
            "documents": len(documents),
            "articles": len(articles),
            "chunks": len(chunks),
        },
        "sha256": {},
        "notes": "Bootstrap integration sample; replace with scraped Adilet text before evaluation.",
    }
    for filename, (rows, schema) in outputs.items():
        path = out_dir / filename
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
        manifest["sha256"][f"sample/{filename}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    sample_json = out_dir / "sample_articles.json"
    sample_json.write_text(
        json.dumps(articles[:30], ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    manifest["sha256"]["sample/sample_articles.json"] = hashlib.sha256(
        sample_json.read_bytes()
    ).hexdigest()
    return manifest


def write_manifest(repo_data_dir: Path, manifest: dict[str, Any]) -> None:
    path = repo_data_dir / "MANIFEST.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/sample"))
    parser.add_argument("--manifest", type=Path, default=Path("data/MANIFEST.json"))
    args = parser.parse_args(argv)
    manifest = write(args.out)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "wrote "
        f"{manifest['row_counts']['documents']} documents, "
        f"{manifest['row_counts']['articles']} articles, "
        f"{manifest['row_counts']['chunks']} chunks to {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
