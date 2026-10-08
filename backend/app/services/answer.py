"""Streamed RAG answer (contracts/api.md `POST /answer`).

prepare(): run the shared search pipeline (errors become a normal JSON response, before any
           stream starts).
stream():  `sources` at once → (zero results: fixed "not found" `done`, no LLM call) →
           relay `/generate` tokens → clean citations → `done` with the authoritative text.
           LLM unavailable / timeout → `error` (generation_unavailable) after the sources.
           Client disconnect → the upstream request is closed and the answer is saved as
           `cancelled`.

The query-log row and the answer row are written together, off the request path, once the stream
ends (whatever the outcome), so the answer's foreign key never races the log write.
"""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from sse_starlette import ServerSentEvent

from app.db.models import Article, Document
from app.schemas.answer import (
    AnswerRequest,
    AnswerSource,
    AnswerTiming,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    TokenEvent,
)
from app.schemas.ml import GenerateRequest, GenerateSource, Manifest
from app.schemas.search import SearchRequest
from app.services.background import BackgroundRunner
from app.services.citations import NOT_FOUND_TEXT, process_citations
from app.services.ml_client import GenerateEvent, MlUnavailable
from app.services.search import AssembledResult, SearchContext, SearchOutcome, SearchService

log = structlog.get_logger(__name__)


class Generator(Protocol):
    def generate_stream(
        self, request: GenerateRequest, *, timeout_s: float
    ) -> AsyncGenerator[GenerateEvent]: ...


class ManifestSource(Protocol):
    async def get(self) -> Manifest | None: ...


class AnswerStore(Protocol):
    async def save(self, log_values: dict[str, Any], answer_values: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class AnswerConfig:
    timeout_s: float = 90.0
    max_tokens: int = 512
    temperature: float = 0.1


@dataclass
class PreparedAnswer:
    outcome: SearchOutcome
    started: float
    sources: list[AssembledResult] = field(default_factory=list)


def truncate_at_paragraph(text: str, limit: int) -> str:
    """At most `limit` chars, cut at the last paragraph break (else word) before the limit."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    if cut <= 0:  # no paragraph break before the limit: fall back to a word boundary
        cut = text.rfind(" ", 0, limit)
    if cut <= 0:
        cut = limit
    return text[:cut].rstrip()


def source_title(article: Article, document: Document) -> str:
    """`«{short_title}. Статья {N}. {title}»` (ru) / `«{short_title}. {N}-бап. {title}»` (kk)."""
    parts = [document.short_title]
    if article.unit_number:
        parts.append(
            f"Статья {article.unit_number}"
            if article.lang == "ru"
            else f"{article.unit_number}-бап"
        )
    if article.unit_title:
        parts.append(article.unit_title)
    return ". ".join(parts)


def sse(event: str, payload: Any) -> ServerSentEvent:
    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    return ServerSentEvent(data=json.dumps(data, ensure_ascii=False), event=event)


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


class AnswerService:
    def __init__(
        self,
        search: SearchService,
        ml: Generator,
        manifest: ManifestSource,
        store: AnswerStore,
        background: BackgroundRunner,
        config: AnswerConfig,
    ) -> None:
        self._search = search
        self._ml = ml
        self._manifest = manifest
        self._store = store
        self._background = background
        self._config = config

    async def prepare(self, request: AnswerRequest, ctx: SearchContext) -> PreparedAnswer:
        """Run search for the sources. Raises SearchError (→ JSON error, no stream)."""
        started = time.perf_counter()
        search_request = SearchRequest.model_validate(
            {**request.model_dump(exclude={"context_top_k"}), "top_k": request.context_top_k}
        )
        outcome = await self._search.search(search_request, ctx)
        return PreparedAnswer(outcome, started, outcome.items[: request.context_top_k])

    async def stream(
        self, request: AnswerRequest, prepared: PreparedAnswer
    ) -> AsyncIterator[ServerSentEvent]:
        response = prepared.outcome.response
        answer_id = uuid.uuid4()
        manifest = await self._manifest.get()
        params = manifest.retrieval if manifest else None
        max_chars = params.max_chars_per_context if params else 4000
        refs = list(range(1, len(prepared.sources) + 1))
        search_ms = response.timing_ms.get("total")
        answer: dict[str, Any] = {
            "answer_id": answer_id,
            "query_id": response.query_id,
            "status": "error",
            "sources": [
                {"ref": ref, "article_id": item.article.article_id}
                for ref, item in zip(refs, prepared.sources, strict=True)
            ],
            "search_ms": search_ms,
            "pipeline_version": response.pipeline_version,
        }
        streamed: list[str] = []
        ttft_ms: int | None = None
        try:
            yield sse(
                "sources",
                SourcesEvent(
                    query_id=response.query_id,
                    lang=response.lang,
                    sources=[
                        AnswerSource(
                            ref=ref,
                            article=item.result.article,
                            doc=item.result.doc,
                            snippet=item.result.snippet,
                        )
                        for ref, item in zip(refs, prepared.sources, strict=True)
                    ],
                    degraded=response.degraded,
                ),
            )

            if not prepared.sources:
                text = NOT_FOUND_TEXT[response.lang]
                total_ms = _ms(time.perf_counter() - prepared.started)
                answer.update(
                    status="completed",
                    text=text,
                    grounded=False,
                    finish_reason="no_results",
                    total_ms=total_ms,
                )
                yield sse(
                    "done",
                    DoneEvent(
                        answer_id=answer_id,
                        text=text,
                        citations=[],
                        invalid_citations_removed=0,
                        grounded=False,
                        finish_reason="no_results",
                        timing_ms=AnswerTiming(search=search_ms, total=total_ms),
                        pipeline_version=response.pipeline_version,
                    ),
                )
                return

            generate = GenerateRequest(
                question=request.query,
                lang=response.lang,
                sources=[
                    GenerateSource(
                        ref=ref,
                        article_id=item.article.article_id,
                        title=source_title(item.article, item.document),
                        text=truncate_at_paragraph(item.article.text, max_chars),
                    )
                    for ref, item in zip(refs, prepared.sources, strict=True)
                ],
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                stream=True,
            )
            final_text: str | None = None
            finish_reason = "stop"
            async with asyncio.timeout(self._config.timeout_s):
                events = self._ml.generate_stream(generate, timeout_s=self._config.timeout_s)
                async with aclosing(events) as upstream:
                    async for event in upstream:
                        if event.event == "token":
                            piece = str(event.data.get("text", ""))
                            if ttft_ms is None:
                                ttft_ms = _ms(time.perf_counter() - prepared.started)
                            streamed.append(piece)
                            yield sse("token", TokenEvent(text=piece))
                        elif event.event == "done":
                            final_text = str(event.data.get("text", "".join(streamed)))
                            finish_reason = str(event.data.get("finish_reason", "stop"))
                            break
                        elif event.event == "error":
                            raise MlUnavailable(
                                "/generate", "upstream_error", str(event.data.get("code", ""))
                            )
            if final_text is None:
                raise MlUnavailable("/generate", "incomplete", "stream ended without done")

            cited = process_citations(final_text, refs)
            total_ms = _ms(time.perf_counter() - prepared.started)
            answer.update(
                status="completed",
                text=cited.text,
                citations=cited.citations,
                invalid_citations_removed=cited.invalid_removed,
                grounded=cited.grounded,
                finish_reason=finish_reason,
                ttft_ms=ttft_ms,
                total_ms=total_ms,
            )
            yield sse(
                "done",
                DoneEvent(
                    answer_id=answer_id,
                    text=cited.text,
                    citations=cited.citations,
                    invalid_citations_removed=cited.invalid_removed,
                    grounded=cited.grounded,
                    finish_reason=finish_reason,
                    timing_ms=AnswerTiming(search=search_ms, ttft=ttft_ms, total=total_ms),
                    pipeline_version=response.pipeline_version,
                ),
            )
        except (MlUnavailable, TimeoutError) as exc:
            kind = exc.kind if isinstance(exc, MlUnavailable) else "timeout"
            log.warning("generation_unavailable", error=str(exc) or kind)
            answer.update(
                status="error",
                error_code="generation_unavailable",
                text="".join(streamed),
                ttft_ms=ttft_ms,
                total_ms=_ms(time.perf_counter() - prepared.started),
            )
            yield sse(
                "error",
                ErrorEvent(
                    code="generation_unavailable",
                    message="The answer generator is unavailable; the sources above are valid.",
                ),
            )
        except (asyncio.CancelledError, GeneratorExit):
            log.info("answer_cancelled", answer_id=str(answer_id))
            answer.update(
                status="cancelled",
                error_code="cancelled",
                text="".join(streamed),
                ttft_ms=ttft_ms,
                total_ms=_ms(time.perf_counter() - prepared.started),
            )
            raise
        except Exception:
            log.exception("answer_failed", answer_id=str(answer_id))
            answer.update(
                status="error",
                error_code="internal_error",
                text="".join(streamed),
                total_ms=_ms(time.perf_counter() - prepared.started),
            )
            yield sse("error", ErrorEvent(code="internal_error", message="Internal error"))
        finally:
            log_values = {
                **prepared.outcome.log_values,
                "has_answer": answer["status"] == "completed",
            }
            if answer["status"] != "completed":
                log_values["error_code"] = answer.get("error_code")
            self._background.spawn(self._store.save(log_values, answer))
