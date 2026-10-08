"""services/citations.py: normalisation, invalid markers, grounded flag (api.md `/answer` rules)."""

import pytest

from app.services.citations import NOT_FOUND_TEXT, is_refusal, process_citations

REFS = [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    ("raw", "text", "citations", "removed"),
    [
        ("Работодатель обязан платить [1].", "Работодатель обязан платить [1].", [1], 0),
        ("См. [1, 2].", "См. [1][2].", [1, 2], 0),
        ("См. [1,3] и [2; 4].", "См. [1][3] и [2][4].", [1, 2, 3, 4], 0),
        ("См. [1][2].", "См. [1][2].", [1, 2], 0),
        ("Норма [12] применяется.", "Норма применяется.", [], 1),
        ("Норма [0].", "Норма.", [], 1),
        ("Смешанно [2, 12, 2].", "Смешанно [2].", [2], 1),
        ("Дубли [1][1] и [1, 1].", "Дубли [1] и [1].", [1], 0),
        ("статья[3]гласит", "статья[3]гласит", [3], 0),  # markers inside words still count
        ("Без ссылок.", "Без ссылок.", [], 0),
        ("Пункт [а] и [1-3] не маркеры [2].", "Пункт [а] и [1-3] не маркеры [2].", [2], 0),
        (
            "Жұмыс беруші жалақыны айына бір рет төлейді [1, 2].",
            "Жұмыс беруші жалақыны айына бір рет төлейді [1][2].",
            [1, 2],
            0,
        ),
        ("Первая строка [9]\nВторая [1]", "Первая строка\nВторая [1]", [1], 1),
    ],
)
def test_process_citations(raw: str, text: str, citations: list[int], removed: int) -> None:
    result = process_citations(raw, REFS)
    assert result.text == text
    assert result.citations == citations
    assert result.invalid_removed == removed
    assert result.grounded is bool(citations)


def test_refusal_makes_answer_ungrounded() -> None:
    result = process_citations("В предоставленных источниках нет ответа на этот вопрос [1].", REFS)
    assert result.citations == [1]
    assert result.refused
    assert not result.grounded


def test_refusal_detection_is_case_and_whitespace_insensitive() -> None:
    assert is_refusal("Берілген  дереккөздерде ЖАУАП жоқ.")
    assert is_refusal("Источники не содержат ответа")
    assert not is_refusal("Работодатель обязан выплатить компенсацию [1].")


def test_not_found_texts_exist_for_both_languages() -> None:
    assert set(NOT_FOUND_TEXT) == {"ru", "kk"}
    assert not process_citations(NOT_FOUND_TEXT["ru"], REFS).grounded
