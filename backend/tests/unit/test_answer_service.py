"""AnswerService: SSE event order and payloads, citations, zero results, failures, disconnect."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_answer_service, get_background, get_query_log_writer
from app.core.errors import APIError
from app.schemas.answer import AnswerRequest, DoneEvent, ErrorEvent, SourcesEvent
from app.schemas.ml import GenerateRequest, Manifest
from app.services.answer import (
    AnswerConfig,
    AnswerService,
    PreparedAnswer,
    source_title,
    truncate_at_paragraph,
)
from app.services.background import BackgroundRunner
from app.services.citations import NOT_FOUND_TEXT
from app.services.ml_client import GenerateEvent, MlUnavailable
from app.services.search import SearchContext, SearchError
from dev.fake_ml.app import fake_manifest
from tests.unit.test_search_service import ROWS, FakeManifest, FakeStore, make_service

QUERY = "Ответственность работодателя за задержку зарплаты"


class FakeGenerator:
    """Scripted /generate stream. `closed` tells whether the upstream stream was closed."""

    def __init__(self, events: list[GenerateEvent], *, delay_s: float = 0.0, fail: bool = False):
        self.events = events
        self.delay_s = delay_s
        self.fail = fail
        self.requests: list[GenerateRequest] = []
        self.closed = False

    async def generate_stream(
        self, request: GenerateRequest, *, timeout_s: float
    ) -> AsyncGenerator[GenerateEvent]:
        self.requests.append(request)
        try:
            if self.fail:
                raise MlUnavailable("/generate", "connection")
            for event in self.events:
                await asyncio.sleep(self.delay_s)
                yield event
        finally:
            self.closed = True


class RecordingStore:
    def __init__(self) -> None:
        self.saved: list[tuple[dict[str, Any], dict[str, Any]]] = []

    async def save(self, log_values: dict[str, Any], answer_values: dict[str, Any]) -> None:
        self.saved.append((log_values, answer_values))


def tokens(*pieces: str, done: str | None = None) -> list[GenerateEvent]:
    events = [GenerateEvent("token", {"text": p}) for p in pieces]
    text = done if done is not None else "".join(pieces)
    events.append(GenerateEvent("done", {"text": text, "finish_reason": "stop"}))
    return events


def build(
    generator: FakeGenerator, store_hits: FakeStore | None = None, timeout_s: float = 5.0
) -> tuple[AnswerService, RecordingStore, BackgroundRunner]:
    search, _, _ = make_service(store=store_hits)
    store = RecordingStore()
    background = BackgroundRunner()
    service = AnswerService(
        search=search,
        ml=generator,
        manifest=FakeManifest(Manifest.model_validate(fake_manifest())),
        store=store,
        background=background,
        config=AnswerConfig(timeout_s=timeout_s),
    )
    return service, store, background


async def run(service: AnswerService, request: AnswerRequest) -> list[tuple[str, dict[str, Any]]]:
    prepared = await service.prepare(request, SearchContext(endpoint="answer"))
    return [(e.event or "", json.loads(e.data)) async for e in service.stream(request, prepared)]


async def test_happy_path_event_order_and_payloads() -> None:
    generator = FakeGenerator(tokens("Работодатель ", "выплачивает ", "компенсацию [1, 2]."))
    service, store, background = build(generator)
    events = await run(service, AnswerRequest(query=QUERY, context_top_k=3))
    names = [name for name, _ in events]
    assert names[0] == "sources"
    assert names[-1] == "done"
    assert set(names[1:-1]) == {"token"}

    sources = SourcesEvent.model_validate(events[0][1])
    assert [s.ref for s in sources.sources] == [1, 2, 3]
    assert sources.lang == "ru"
    done = DoneEvent.model_validate(events[-1][1])
    assert done.text == "Работодатель выплачивает компенсацию [1][2]."
    assert done.citations == [1, 2]
    assert done.grounded
    assert done.invalid_citations_removed == 0
    assert done.timing_ms.ttft is not None
    assert done.timing_ms.search is not None
    assert done.pipeline_version == "0.0.0-fake"

    # The generator got the full article texts and contract-style titles.
    sent = generator.requests[0]
    assert len(sent.sources) == 3
    first = sources.sources[0].article.article_id
    assert sent.sources[0].article_id == first
    assert sent.sources[0].text == ROWS[first][0].text
    assert sent.sources[0].title.startswith("Тестовый ТК. Статья ")

    await background.drain()
    log_values, answer = store.saved[0]
    assert answer["status"] == "completed"
    assert answer["query_id"] == sources.query_id == log_values["query_id"]
    assert answer["citations"] == [1, 2]
    assert log_values["has_answer"] is True
    assert log_values["endpoint"] == "answer"


async def test_invalid_citations_are_removed_and_counted() -> None:
    generator = FakeGenerator(tokens("Ответ [1] и [9]."))
    service, _, _ = build(generator)
    events = await run(service, AnswerRequest(query=QUERY, context_top_k=2))
    done = DoneEvent.model_validate(events[-1][1])
    assert done.text == "Ответ [1] и."
    assert done.invalid_citations_removed == 1
    assert done.citations == [1]


async def test_done_text_from_ml_is_authoritative() -> None:
    generator = FakeGenerator(tokens("черновик ", done="Итоговый текст [1]."))
    service, _, _ = build(generator)
    events = await run(service, AnswerRequest(query=QUERY))
    assert DoneEvent.model_validate(events[-1][1]).text == "Итоговый текст [1]."


async def test_refusal_is_not_grounded() -> None:
    generator = FakeGenerator(tokens("В предоставленных источниках нет ответа на вопрос."))
    service, _, _ = build(generator)
    done = DoneEvent.model_validate((await run(service, AnswerRequest(query=QUERY)))[-1][1])
    assert not done.grounded
    assert done.citations == []


async def test_zero_results_skips_the_llm() -> None:
    generator = FakeGenerator(tokens("never"))
    service, store, background = build(generator, store_hits=FakeStore([], []))
    events = await run(service, AnswerRequest(query=QUERY))
    assert [name for name, _ in events] == ["sources", "done"]
    assert SourcesEvent.model_validate(events[0][1]).sources == []
    done = DoneEvent.model_validate(events[1][1])
    assert done.text == NOT_FOUND_TEXT["ru"]
    assert not done.grounded
    assert generator.requests == []
    await background.drain()
    assert store.saved[0][1]["status"] == "completed"


@pytest.mark.parametrize(
    "generator",
    [
        FakeGenerator(
            [
                GenerateEvent("token", {"text": "Начало "}),
                GenerateEvent("error", {"code": "llm_unavailable", "message": "x"}),
            ]
        ),
        FakeGenerator([], fail=True),
        FakeGenerator([GenerateEvent("token", {"text": "обрыв"})]),  # stream ends without done
    ],
    ids=["error-event", "connection", "incomplete"],
)
async def test_generation_failure_sends_error_after_sources(generator: FakeGenerator) -> None:
    service, store, background = build(generator)
    events = await run(service, AnswerRequest(query=QUERY))
    names = [name for name, _ in events]
    assert names[0] == "sources"
    assert names[-1] == "error"
    assert "done" not in names
    assert ErrorEvent.model_validate(events[-1][1]).code == "generation_unavailable"
    await background.drain()
    log_values, answer = store.saved[0]
    assert answer["status"] == "error"
    assert answer["error_code"] == "generation_unavailable"
    assert log_values["has_answer"] is False
    assert log_values["error_code"] == "generation_unavailable"


async def test_timeout_sends_error() -> None:
    generator = FakeGenerator(tokens("медленно"), delay_s=0.5)
    service, _, _ = build(generator, timeout_s=0.05)
    events = await run(service, AnswerRequest(query=QUERY))
    assert events[-1][0] == "error"
    assert generator.closed


async def test_disconnect_closes_upstream_and_is_logged_as_cancelled() -> None:
    generator = FakeGenerator(tokens("раз ", "два ", "три [1]."), delay_s=0.01)
    service, store, background = build(generator)
    request = AnswerRequest(query=QUERY)
    prepared = await service.prepare(request, SearchContext(endpoint="answer"))
    stream = service.stream(request, prepared)
    assert (await anext(stream)).event == "sources"
    assert (await anext(stream)).event == "token"
    await stream.aclose()  # what the SSE response does when the client goes away
    assert generator.closed
    await background.drain()
    _, answer = store.saved[0]
    assert answer["status"] == "cancelled"
    assert answer["text"] == "раз "


def test_truncate_at_paragraph() -> None:
    text = "Первый абзац.\nВторой абзац подлиннее.\nТретий."
    assert truncate_at_paragraph(text, 1000) == text
    assert truncate_at_paragraph(text, 30) == "Первый абзац."
    assert truncate_at_paragraph("одно длинное предложение без переносов", 20) == "одно длинное"
    assert len(truncate_at_paragraph("x" * 50, 10)) == 10


def test_source_title() -> None:
    article, document = ROWS["T0000000001:kk:a113"]
    assert (
        source_title(article, document)
        == "Сынақ ЕК. 113-бап. Жалақыны төлеу мерзімдері мен тәртібі"
    )
    article, document = ROWS["T0000000001:ru:a113"]
    assert (
        source_title(article, document)
        == "Тестовый ТК. Статья 113. Сроки и порядок выплаты заработной платы"
    )


# --- the HTTP endpoint ------------------------------------------------------------------------


def parse_sse(raw: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in raw.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


class Recorder:
    def __init__(self) -> None:
        self.rows: list[Any] = []

    async def write(self, values: Any) -> None:
        self.rows.append(values)


def test_endpoint_streams_sse(app: FastAPI, client: TestClient) -> None:
    service, _, _ = build(FakeGenerator(tokens("Ответ [1].")))
    app.dependency_overrides[get_answer_service] = lambda: service
    with client.stream("POST", "/api/v1/answer", json={"query": QUERY}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-request-id"]
        events = parse_sse(response.read().decode("utf-8"))
    assert [e[0] for e in events] == ["sources", "token", "done"]


def test_endpoint_validation_is_plain_json(client: TestClient) -> None:
    response = client.post("/api/v1/answer", json={"query": QUERY, "context_top_k": 0})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")


def test_endpoint_search_failure_is_plain_json_and_logged(app: FastAPI, client: TestClient) -> None:
    class Failing:
        async def prepare(self, request: AnswerRequest, ctx: SearchContext) -> PreparedAnswer:
            raise SearchError(APIError(503, "down", code="upstream_unavailable"), {"q": 1})

    recorder = Recorder()
    background = BackgroundRunner()
    app.dependency_overrides[get_answer_service] = lambda: Failing()
    app.dependency_overrides[get_query_log_writer] = lambda: recorder
    app.dependency_overrides[get_background] = lambda: background
    response = client.post("/api/v1/answer", json={"query": QUERY})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"


def test_heartbeat_is_a_ping_comment() -> None:
    from app.api.v1.answer import _ping

    encoded = _ping().encode().decode()
    assert encoded.replace("\r\n", "\n") == ": ping\n\n"
