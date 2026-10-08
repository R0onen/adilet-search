"""Language detection, snippets/highlights, Qdrant filters, query-log helpers."""

from datetime import date

import pytest
from qdrant_client import models as qm

from app.services.lang import detect_lang, resolve_lang
from app.services.qdrant_store import SearchFilter, build_filter, date_to_int
from app.services.query_log import normalise_query, session_hash
from app.services.snippets import SNIPPET_MAX_CHARS, highlights, make_snippet

# --- language -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Ответственность работодателя за задержку зарплаты", "ru"),
        ("Еңбек шартын бұзу негіздері", "kk"),
        ("ЖАЛАҚЫ", "kk"),  # upper-case Kazakh letter
        ("Статья 113 ТК", "ru"),
        ("labour code", "ru"),  # no Kazakh letters -> ru
        ("Іс", "kk"),
    ],
)
def test_detect_lang(text: str, lang: str) -> None:
    assert detect_lang(text) == lang


def test_resolve_lang_respects_explicit_choice() -> None:
    assert resolve_lang("ru", "Еңбек шарты") == "ru"
    assert resolve_lang("auto", "Еңбек шарты") == "kk"


# --- snippets -----------------------------------------------------------------------------

LONG = (
    "1. Настоящая статья регулирует общие вопросы. "
    "2. Работодатель обязан соблюдать трудовое законодательство. "
    "3. За задержку выплаты заработной платы работодатель выплачивает компенсацию. "
    "4. Порядок расчёта устанавливается уполномоченным органом. " * 3
)


def test_short_text_is_returned_whole() -> None:
    assert make_snippet("Короткий текст.", "текст") == "Короткий текст."


def test_snippet_is_bounded_and_verbatim() -> None:
    snippet = make_snippet(LONG, "задержка зарплаты")
    assert len(snippet) <= SNIPPET_MAX_CHARS
    assert "задержку выплаты заработной платы" in snippet
    assert snippet.strip("…") in LONG  # an excerpt, never rewritten


def test_snippet_of_one_huge_sentence_centres_on_the_match() -> None:
    text = "слово " * 200 + "задержка зарплаты " + "слово " * 200
    snippet = make_snippet(text, "задержка")
    assert len(snippet) <= SNIPPET_MAX_CHARS
    assert "задержка" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")


def test_highlights_match_inflected_forms() -> None:
    snippet = "Работодатель выплачивает заработную плату за каждый день задержки."
    spans = highlights(snippet, "Ответственность работодателя за задержку зарплаты")
    words = [snippet[s.start : s.end] for s in spans]
    assert "Работодатель" in words
    assert "задержки" in words
    assert "за" not in words  # too short to highlight


def test_highlights_kazakh() -> None:
    snippet = "Жалақыны кешіктіргені үшін жұмыс беруші жауап береді."
    words = [snippet[s.start : s.end] for s in highlights(snippet, "жалақы кешіктіру")]
    assert words == ["Жалақыны", "кешіктіргені"]


def test_no_terms_no_highlights() -> None:
    assert highlights("Любой текст", "и в") == []


# --- Qdrant filter ------------------------------------------------------------------------


def _conditions(f: qm.Filter) -> dict[str, qm.FieldCondition]:
    assert f.must is not None
    return {c.key: c for c in f.must if isinstance(c, qm.FieldCondition)}


def test_filter_defaults_language_and_in_force() -> None:
    conditions = _conditions(build_filter(SearchFilter(lang="kk")))
    assert set(conditions) == {"lang", "doc_status", "unit_status"}
    assert conditions["lang"].match == qm.MatchValue(value="kk")
    assert conditions["doc_status"].match == qm.MatchValue(value="in_force")
    assert conditions["unit_status"].match == qm.MatchValue(value="in_force")


def test_filter_all_options() -> None:
    f = SearchFilter(
        lang="ru",
        doc_ids=["K1500000414"],
        doc_types=["code", "law"],
        in_force_only=False,
        date_from=date(2015, 1, 1),
        date_to=date(2020, 12, 31),
    )
    conditions = _conditions(build_filter(f))
    assert set(conditions) == {"lang", "doc_id", "doc_type", "adopted_date"}
    assert conditions["doc_type"].match == qm.MatchAny(any=["code", "law"])
    assert conditions["adopted_date"].range == qm.Range(gte=20150101, lte=20201231)


def test_open_date_range() -> None:
    conditions = _conditions(build_filter(SearchFilter(lang="ru", date_from=date(2020, 1, 2))))
    assert conditions["adopted_date"].range == qm.Range(gte=20200102, lte=None)
    assert date_to_int(None) is None


# --- query log helpers --------------------------------------------------------------------


def test_session_hash_is_salted_and_stable() -> None:
    a = session_hash("2f1c7a3e-0000-4000-8000-000000000001", "salt-1")
    assert a == session_hash("2f1c7a3e-0000-4000-8000-000000000001", "salt-1")
    assert a != session_hash("2f1c7a3e-0000-4000-8000-000000000001", "salt-2")
    assert a is not None
    assert len(a) == 64
    assert "2f1c7a3e" not in a


@pytest.mark.parametrize("bad", [None, "", "x" * 129])
def test_session_hash_ignores_missing_or_oversized_ids(bad: str | None) -> None:
    assert session_hash(bad, "salt") is None


def test_normalise_query() -> None:
    assert normalise_query("  Задержка\tЗАРПЛАТЫ \n  штраф ") == "задержка зарплаты штраф"


# --- user-agent family ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ua", "family"),
    [
        (None, None),
        ("Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/141.0 Safari/537.36", "chrome"),
        ("Mozilla/5.0 Chrome/141.0 Safari/537.36 Edg/141.0", "edge"),
        ("Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15", "safari"),
        ("Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0", "firefox"),
        ("Mozilla/5.0 Chrome/138.0 YaBrowser/25.8 Safari/537.36", "yandex"),
        ("curl/8.9.1", "curl"),
        ("python-httpx/0.28.1", "python"),
        ("GuzzleHttp/7 PHP/8.3", "php"),
        ("SomethingElse/1.0", "other"),
    ],
)
def test_ua_family(ua: str | None, family: str | None) -> None:
    from app.api.context import ua_family

    assert ua_family(ua) == family
