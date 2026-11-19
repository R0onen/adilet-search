"""Citation post-processing for generated answers (contracts/api.md `/answer`, rules).

- A citation marker is `[n]` where `n` is a source `ref`. `[1, 3]`, `[1,3]`, `[1; 3]` and `[1][3]`
  are all normalised to `[1][3]`.
- Numbers that are not a source ref (`[0]`, `[12]` with 5 sources) are removed and counted.
- `citations` = the sorted unique refs left in the final text.
- `grounded` is false when no valid citation remains or the model used a refusal phrase.

Only bracketed lists of integers are treated as markers; any other bracketed text is left alone.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass

# "[1]", "[1, 3]", "[ 2 ;4 ]"
_MARKER = re.compile(r"\[\s*\d{1,3}(?:\s*[,;]\s*\d{1,3})*\s*\]")
_UNICODE_MARKER = re.compile(r"[【［](\s*\d{1,3}(?:\s*[,;]\s*\d{1,3})*\s*)[】］]")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")
_DOUBLE_SPACES = re.compile(r"[ \t]{2,}")

# Phrases the prompt template (ml/prompts/answer_v1.md) tells the model to open with when the
# sources do not directly answer; the older wordings are kept for stored answers and other models.
REFUSAL_PHRASES = (
    # ru
    "в найденных статьях нет прямого ответа",
    "в предоставленных источниках нет ответа",
    "в источниках нет ответа",
    "источники не содержат ответа",
    "предоставленные источники не содержат",
    "не могу ответить на основании предоставленных источников",
    # kk
    "табылған баптарда бұл сұраққа тікелей жауап жоқ",
    "берілген дереккөздерде жауап жоқ",
    "дереккөздерде жауап жоқ",
    "берілген дереккөздерде бұл сұраққа жауап жоқ",
)

NOT_FOUND_TEXT = {
    "ru": "По вашему запросу в базе законодательства не найдено подходящих статей. "
    "Попробуйте переформулировать вопрос.",
    # Needs a native-speaker check (UI text, not statute text).
    "kk": "Сұрауыңыз бойынша заңнама базасынан сәйкес баптар табылмады. "
    "Сұрақты басқаша тұжырымдап көріңіз.",
}


@dataclass(frozen=True, slots=True)
class CitationResult:
    text: str
    citations: list[int]
    invalid_removed: int
    refused: bool

    @property
    def grounded(self) -> bool:
        return bool(self.citations) and not self.refused


def _normalise_for_match(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


NO_DIRECT_ANSWER = {
    "ru": "В найденных статьях нет прямого ответа на этот вопрос.",
    "kk": "Табылған баптарда бұл сұраққа тікелей жауап жоқ.",
}


def localise_no_direct_answer(text: str, lang: str) -> str:
    """The model sometimes writes the fixed "no direct answer" sentence of the other language
    (seen in Kazakh answers). Replace it with the one in the answer's language."""
    target = NO_DIRECT_ANSWER.get(lang)
    if target is None:
        return text
    for other_lang, sentence in NO_DIRECT_ANSWER.items():
        if other_lang != lang and sentence in text:
            text = text.replace(sentence, target)
    return text


def is_refusal(text: str) -> bool:
    normalised = _normalise_for_match(text)
    return any(phrase in normalised for phrase in REFUSAL_PHRASES)


def process_citations(text: str, valid_refs: Collection[int]) -> CitationResult:
    # Some generators use Unicode citation brackets despite the prompt. Normalise only
    # numeric references; quoted statute text in the source records is never modified.
    text = _UNICODE_MARKER.sub(lambda match: f"[{match[1]}]", text)
    valid = set(valid_refs)
    invalid = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal invalid
        numbers = [int(n) for n in re.findall(r"\d+", match.group())]
        kept: list[int] = []
        for n in numbers:
            if n not in valid:
                invalid += 1
            elif n not in kept:
                kept.append(n)
        return "".join(f"[{n}]" for n in kept)

    cleaned = _MARKER.sub(replace, text)
    # Merge adjacent markers into one run and drop duplicates in that run: "[1][1]" -> "[1]".
    cleaned = re.sub(
        r"(?:\[\d+\]){2,}",
        lambda m: "".join(f"[{n}]" for n in dict.fromkeys(re.findall(r"\d+", m.group()))),
        cleaned,
    )
    if invalid:
        cleaned = _SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
        cleaned = _DOUBLE_SPACES.sub(" ", cleaned)
        cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
    cleaned = cleaned.strip()
    citations = sorted({int(n) for n in re.findall(r"\[(\d+)\]", cleaned) if int(n) in valid})
    return CitationResult(
        text=cleaned,
        citations=citations,
        invalid_removed=invalid,
        refused=is_refusal(cleaned),
    )
