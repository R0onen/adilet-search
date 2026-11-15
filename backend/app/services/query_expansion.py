"""Everyday words → the terms the statutes use.

People write "зарплата", "вещдок" or "декрет"; the law says "заработная плата", "вещественные
доказательства", "отпуск по беременности и родам". Neither the keyword side of the search nor
the reranker can match a word that is not in the article, so the query that goes to the models
gets the legal terms appended. The user's own words are never removed, and the query that is
logged, cached and shown stays exactly as typed.

The list is short on purpose: each entry is a common word with one settled legal equivalent.
"""

import re
from typing import NamedTuple


class Rule(NamedTuple):
    pattern: re.Pattern[str]
    terms: str


def _rules(pairs: list[tuple[str, str]]) -> list[Rule]:
    return [Rule(re.compile(pattern, re.IGNORECASE), terms) for pattern, terms in pairs]


# Word starts are matched with (?<!\w) so that "чек" does not fire inside "чековый".
RULES: dict[str, list[Rule]] = {
    "ru": _rules(
        [
            (r"(?<!\w)зарплат\w*|(?<!\w)зп(?!\w)|(?<!\w)получк\w*", "заработная плата"),
            (
                r"(?<!\w)задерж\w+\s+(?:зарплат|выплат)\w*|не\s+плат\w+\s+зарплат\w*|не\s+выплачива\w+",
                "сроки выплаты заработной платы задолженность пеня",
            ),
            (r"(?<!\w)вещдок\w*", "вещественные доказательства"),
            (r"(?<!\w)декрет\w*", "отпуск по беременности и родам отпуск по уходу за ребенком"),
            (r"(?<!\w)больничн\w*", "временная нетрудоспособность"),
            (
                r"(?<!\w)уволить?ся|(?<!\w)увольня\w+сь|(?<!\w)уволил(?:ся|ась)",
                "расторжение трудового договора по инициативе работника",
            ),
            (
                r"(?<!\w)увол(?:ил[иа]?|ить|ен\w*|ьня[юе]т|ьнение)(?!\w)",
                "расторжение трудового договора по инициативе работодателя",
            ),
            (
                r"(?<!\w)сокращени\w+\s+(?:штат|работник)\w*",
                "сокращение численности или штата работников",
            ),
            (r"(?<!\w)отпускн\w+", "оплата ежегодного трудового отпуска"),
            (r"(?<!\w)сверхурочк\w*|(?<!\w)переработк\w*", "сверхурочная работа"),
            (r"(?<!\w)развод\w*|(?<!\w)развест\w*", "расторжение брака"),
            (r"(?<!\w)прописк\w*", "регистрация по месту жительства"),
            (r"(?<!\w)дтп(?!\w)|(?<!\w)авари\w+", "дорожно-транспортное происшествие"),
            (r"(?<!\w)взятк\w*", "получение взятки дача взятки"),
            (
                r"(?<!\w)верну\w+\s+товар\w*|возврат\w*\s+товар\w*|(?<!\w)без\s+чека",
                "обмен или возврат товара потребителем",
            ),
            (r"(?<!\w)ип(?!\w)", "индивидуальный предприниматель"),
            (r"(?<!\w)тоо(?!\w)", "товарищество с ограниченной ответственностью"),
            (r"(?<!\w)ндс(?!\w)", "налог на добавленную стоимость"),
            (r"(?<!\w)ипн(?!\w)", "индивидуальный подоходный налог"),
            (r"(?<!\w)кпн(?!\w)", "корпоративный подоходный налог"),
            (r"(?<!\w)мрп(?!\w)", "месячный расчетный показатель"),
            (r"(?<!\w)мзп(?!\w)", "минимальный размер месячной заработной платы"),
            (
                r"(?<!\w)арест\w*\s+(?:счет|счёт|карт)\w*",
                "арест на имущество должника исполнительное производство",
            ),
            (r"(?<!\w)коллектор\w*", "коллекторская деятельность взыскание задолженности"),
            (r"(?<!\w)банкрот\w*", "банкротство восстановление платежеспособности"),
            (
                r"(?<!\w)съемн\w+\s+квартир\w*|(?<!\w)аренд\w+\s+квартир\w*|снима\w+\s+квартир\w*",
                "наем жилища",
            ),
            (r"(?<!\w)завещан\w*|(?<!\w)наследств\w*", "наследование"),
            (
                r"(?<!\w)права\s+(?:отобра|лиши|забра)\w*",
                "лишение права управления транспортными средствами",
            ),
        ]
    ),
    "kk": _rules(
        [
            (r"(?<!\w)айлық\w*|(?<!\w)жалақы\w*", "жалақы төлеу тәртібі мен мерзімдері"),
            (r"(?<!\w)декрет\w*", "жүктілікке және босануға байланысты демалыс"),
            (r"(?<!\w)ажырас\w*", "некені бұзу"),
            (r"(?<!\w)жұмыстан\s+шығар\w*", "еңбек шартын бұзу тоқтату"),
            (r"(?<!\w)алимент\w*", "алимент төлеу"),
            (r"(?<!\w)мұра\w*", "мұрагерлік"),
        ]
    ),
}

MAX_ADDED_CHARS = 300


def expand_query(query: str, lang: str) -> str:
    """The query for the models: the user's text plus the legal terms for the everyday words in it.
    Returns the query unchanged when nothing applies."""
    added: list[str] = []
    lowered = query.lower()
    for rule in RULES.get(lang, []):
        if rule.pattern.search(query) and rule.terms not in added and rule.terms not in lowered:
            added.append(rule.terms)
    if not added:
        return query
    extra = " ".join(added)[:MAX_ADDED_CHARS]
    return f"{query.strip()} ({extra})"
