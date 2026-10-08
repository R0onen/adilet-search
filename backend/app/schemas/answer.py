"""`POST /answer` request and the Server-Sent Event payloads (contracts/api.md §3)."""

from uuid import UUID

from pydantic import Field

from app.schemas.common import ArticleRef, ContractModel, Degraded, DocumentRef, Lang
from app.schemas.search import SearchRequest


class AnswerRequest(SearchRequest):
    context_top_k: int = Field(
        default=5, ge=1, le=8, description="How many top articles are given to the generator"
    )


class AnswerSource(ContractModel):
    ref: int = Field(ge=1, description="The `n` used in `[n]` citations")
    article: ArticleRef
    doc: DocumentRef
    snippet: str


class SourcesEvent(ContractModel):
    """`event: sources` (sent once, first)."""

    query_id: UUID
    lang: Lang
    sources: list[AnswerSource]
    degraded: list[Degraded] = Field(default_factory=list)


class TokenEvent(ContractModel):
    """`event: token` (sent many times)."""

    text: str


class AnswerTiming(ContractModel):
    search: int | None = None
    ttft: int | None = None
    total: int | None = None


class DoneEvent(ContractModel):
    """`event: done` (sent once, last). `text` is authoritative and replaces the streamed text."""

    answer_id: UUID
    text: str
    citations: list[int] = Field(description="Sorted unique source refs cited in `text`")
    invalid_citations_removed: int = Field(ge=0)
    grounded: bool
    finish_reason: str = Field(examples=["stop"])
    timing_ms: AnswerTiming
    pipeline_version: str | None = None


class ErrorEvent(ContractModel):
    """`event: error` (sent instead of `done` when generation fails after the stream started)."""

    code: str = Field(
        description="`generation_unavailable` or `internal_error`",
        examples=["generation_unavailable"],
    )
    message: str


SSE_EVENTS: dict[str, type[ContractModel]] = {
    "sources": SourcesEvent,
    "token": TokenEvent,
    "done": DoneEvent,
    "error": ErrorEvent,
}
