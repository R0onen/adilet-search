"""Every example in contracts/api.md validates against the backend models and round-trips.

Blocks are matched to models in document order. When the contract gains or loses an example,
this test fails until EXPECTED is updated, so the models and the document cannot drift apart.

Placeholders used in the contract for brevity are resolved before validation:
- the strings "ArticleRef", "DocumentRef", "SearchResult" become the examples of those objects;
- "Job | null" becomes null; a list item "…" ("and more") is dropped;
- the `/admin/queries/{query_id}` example lists only the fields added to the list item.
"""

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel

from app.schemas.admin import (
    Job,
    JobRef,
    LoginRequest,
    QueryLogDetail,
    QueryLogItem,
    ReindexRequest,
    StatsResponse,
    SystemResponse,
    TokenResponse,
)
from app.schemas.answer import DoneEvent, ErrorEvent, SourcesEvent, TokenEvent
from app.schemas.common import ArticleRef, DocumentRef, ErrorResponse, SearchResult
from app.schemas.documents import ArticleDetail
from app.schemas.feedback import FeedbackRequest
from app.schemas.health import HealthResponse, VersionResponse
from app.schemas.search import SearchRequest, SearchResponse
from tests.conftest import CONTRACTS

API_MD = CONTRACTS / "api.md"
FENCE = re.compile(r"^\s*```(\w*)\s*$")
HEADING = re.compile(r"^(#{1,4} .+|\*\*[A-Za-z]+\*\*)\s*$")
INLINE_OBJECT = re.compile(r"`(\{.*?\})`")
INLINE_SECTIONS = ("POST /admin/login", "POST /admin/reindex")


@dataclass
class Example:
    heading: str
    kind: str  # json | sse | inline
    data: Any
    event: str | None = None


def extract_examples(text: str) -> list[Example]:
    examples: list[Example] = []
    heading = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if HEADING.match(line):
            heading = line.strip("#* ").strip()
        fence = FENCE.match(line)
        if fence:
            lang = fence.group(1)
            body: list[str] = []
            i += 1
            while not FENCE.match(lines[i]):
                body.append(lines[i].strip())
                i += 1
            if lang == "json":
                examples.append(Example(heading, "json", json.loads("\n".join(body))))
            elif any(b.startswith("data: ") for b in body):
                event = next(b for b in body if b.startswith("event: "))[7:]
                raw = next(b for b in body if b.startswith("data: "))[6:]
                raw = re.sub(r'(?<=": )(ArticleRef|DocumentRef)\b', r'"\1"', raw)
                examples.append(Example(heading, "sse", json.loads(raw), event))
        elif any(section in heading for section in INLINE_SECTIONS):
            for match in INLINE_OBJECT.finditer(line):
                examples.append(Example(heading, "inline", json.loads(match.group(1))))
        i += 1
    return examples


EXAMPLES = extract_examples(API_MD.read_text(encoding="utf-8"))

# (heading substring, model) in document order.
EXPECTED: list[tuple[str, type[BaseModel]]] = [
    ("1. Conventions", ErrorResponse),
    ("DocumentRef", DocumentRef),
    ("ArticleRef", ArticleRef),
    ("SearchResult", SearchResult),
    ("POST /search", SearchRequest),
    ("POST /search", SearchResponse),
    ("POST /answer", SourcesEvent),
    ("POST /answer", TokenEvent),
    ("POST /answer", DoneEvent),
    ("POST /answer", ErrorEvent),
    ("GET /articles/{article_id}", ArticleDetail),
    ("POST /feedback", FeedbackRequest),
    ("GET /health", HealthResponse),
    ("GET /version", VersionResponse),
    ("POST /admin/login", LoginRequest),
    ("POST /admin/login", TokenResponse),
    ("GET /admin/stats", StatsResponse),
    ("GET /admin/queries", QueryLogItem),
    ("GET /admin/queries/{query_id}", QueryLogDetail),
    ("GET /admin/system", SystemResponse),
    ("POST /admin/reindex", ReindexRequest),
    ("POST /admin/reindex", JobRef),
    ("GET /admin/jobs/{job_id}", Job),
]


def _by_model(model: type[BaseModel]) -> Any:
    index = next(i for i, (_, m) in enumerate(EXPECTED) if m is model)
    return EXAMPLES[index].data


def resolve(value: Any) -> Any:
    placeholders = {
        "DocumentRef": lambda: _by_model(DocumentRef),
        "ArticleRef": lambda: _by_model(ArticleRef),
        "SearchResult": lambda: resolve(_by_model(SearchResult)),
        "Job | null": lambda: None,
    }
    if isinstance(value, str) and value in placeholders:
        return copy.deepcopy(placeholders[value]())
    if isinstance(value, list):
        return [resolve(item) for item in value if item != "…"]
    if isinstance(value, dict):
        return {key: resolve(item) for key, item in value.items()}
    return value


def test_example_inventory_matches() -> None:
    found = [(e.heading, e.kind) for e in EXAMPLES]
    assert len(EXAMPLES) == len(EXPECTED), found
    for example, (heading, _) in zip(EXAMPLES, EXPECTED, strict=True):
        assert heading in example.heading, (example.heading, heading)


def test_sse_examples_name_their_events() -> None:
    events = [e.event for e in EXAMPLES if e.kind == "sse"]
    assert events == ["sources", "token", "done", "error"]


@pytest.mark.parametrize(
    ("index", "model"),
    [(i, model) for i, (_, model) in enumerate(EXPECTED)],
    ids=[f"{i:02d}-{model.__name__}" for i, (_, model) in enumerate(EXPECTED)],
)
def test_example_round_trips(index: int, model: type[BaseModel]) -> None:
    data = resolve(EXAMPLES[index].data)
    if model is QueryLogDetail:
        data = {**resolve(_by_model(QueryLogItem)), **data}
    parsed = model.model_validate(data)
    assert parsed.model_dump(mode="json", exclude_unset=True) == data
