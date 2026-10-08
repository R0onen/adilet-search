from pathlib import Path

import pyarrow.parquet as pq

from adilet_ml.ingest.adilet import parse_html
from adilet_ml.ingest.corpus import build_from_cached_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ru_article_markers() -> None:
    html = (FIXTURES / "adilet_ru_labor_sample.html").read_text(encoding="utf-8")
    parsed = parse_html(html, "ru")
    assert parsed.title == "Трудовой кодекс Республики Казахстан"
    assert [article.unit_number for article in parsed.articles] == ["52", "53", "113-1"]
    assert parsed.articles[1].unit_status == "excluded"
    assert parsed.articles[2].amendment_notes == [
        "Сноска. Статья 113-1 с изменениями для теста."
    ]
    assert "Сноска" not in parsed.articles[2].text


def test_parse_kk_article_markers() -> None:
    html = (FIXTURES / "adilet_kk_labor_sample.html").read_text(encoding="utf-8")
    parsed = parse_html(html, "kk")
    assert parsed.title == "Қазақстан Республикасының Еңбек кодексі"
    assert [article.unit_number for article in parsed.articles] == ["52", "53", "113-1"]
    assert parsed.articles[1].unit_status == "excluded"
    assert parsed.articles[2].amendment_notes == [
        "Ескерту. 113-1-бапқа тест үшін өзгерістер енгізілді."
    ]
    assert "Ескерту" not in parsed.articles[2].text


def test_build_from_cached_html(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "adilet"
    (raw / "ru").mkdir(parents=True)
    (raw / "kk").mkdir(parents=True)
    (raw / "ru" / "K1500000414.html").write_text(
        (FIXTURES / "adilet_ru_labor_sample.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (raw / "kk" / "K1500000414.html").write_text(
        (FIXTURES / "adilet_kk_labor_sample.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    config = tmp_path / "corpus.yaml"
    config.write_text(
        """
corpus_version: "test"
acts:
  - key: labor
    doc_id: K1500000414
    short_title_ru: "ТК РК"
    short_title_kk: "ҚР ЕК"
    doc_type: code
    tier: 1
    languages: [ru, kk]
""",
        encoding="utf-8",
    )
    manifest = build_from_cached_html(
        config_path=config,
        raw_dir=tmp_path / "raw",
        out_dir=tmp_path / "processed",
        max_chunk_tokens=20,
    )
    assert manifest["row_counts"] == {"documents": 2, "articles": 6, "chunks": 6}
    articles = pq.read_table(tmp_path / "processed" / "articles.parquet").to_pylist()
    assert {row["article_id"] for row in articles} >= {
        "K1500000414:ru:a113-1",
        "K1500000414:kk:a113-1",
    }
