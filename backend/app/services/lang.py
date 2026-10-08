"""Query language detection (contracts/api.md `/search`, field `lang`)."""

from typing import Literal

# Letters that exist in Kazakh Cyrillic but not in Russian.
KAZAKH_LETTERS = frozenset("әғқңөұүһіӘҒҚҢӨҰҮҺІ")


def detect_lang(text: str) -> Literal["ru", "kk"]:
    return "kk" if any(char in KAZAKH_LETTERS for char in text) else "ru"


def resolve_lang(requested: Literal["auto", "ru", "kk"], query: str) -> Literal["ru", "kk"]:
    return detect_lang(query) if requested == "auto" else requested
