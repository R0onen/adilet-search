import pytest

from app.services.query_expansion import MAX_ADDED_CHARS, expand_query


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("работодатель задерживает зарплату — что делать?", "заработная плата"),
        ("работодатель задерживает зарплату — что делать?", "сроки выплаты заработной платы"),
        ("сколько могут держать телефон в вещдоке", "вещественные доказательства"),
        ("можно ли вернуть товар в магазин без чека", "обмен или возврат товара потребителем"),
        ("как открыть ИП", "индивидуальный предприниматель"),
        ("Ставка НДС", "налог на добавленную стоимость"),
        ("меня хотят уволить", "по инициативе работодателя"),
        ("хочу уволиться", "по инициативе работника"),
    ],
)
def test_everyday_words_get_the_legal_terms(query: str, expected: str) -> None:
    expanded = expand_query(query, "ru")
    assert expanded.startswith(query)
    assert expected in expanded


@pytest.mark.parametrize(
    "query",
    [
        "Законный представитель физического лица",
        "типовой договор",  # "ип" inside a word
        "чековая книжка",
        "",
    ],
)
def test_other_queries_are_unchanged(query: str) -> None:
    assert expand_query(query, "ru") == query


def test_resigning_is_not_dismissal() -> None:
    assert "работодателя" not in expand_query("хочу уволиться", "ru")
    assert "работника" not in expand_query("меня уволили", "ru")


def test_terms_already_in_the_query_are_not_repeated() -> None:
    query = "зарплата это заработная плата?"
    assert expand_query(query, "ru") == query


def test_rules_are_per_language() -> None:
    assert "некені бұзу" in expand_query("ажырасу тәртібі", "kk")
    assert expand_query("ажырасу тәртібі", "ru") == "ажырасу тәртібі"


def test_the_addition_is_bounded() -> None:
    query = (
        "зарплата вещдок декрет больничный уволили развод прописка дтп взятка ип тоо ндс ипн кпн"
    )
    assert len(expand_query(query, "ru")) <= len(query) + MAX_ADDED_CHARS + 3
