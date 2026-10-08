"""Admin endpoints (contracts/api.md §4)."""

import datetime as dt
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.answer import AnswerTiming
from app.schemas.common import ContractModel, Degraded, Lang, PageMeta, SearchMode
from app.schemas.feedback import FeedbackTarget
from app.schemas.health import Components
from app.schemas.search import SearchFilters, SearchTiming

# --- auth ---


class LoginRequest(ContractModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(ContractModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int = Field(description="Seconds until the token expires", examples=[28800])


# --- stats ---


class StatsTotals(ContractModel):
    queries: int
    unique_sessions: int
    answers: int
    feedback_positive: int
    feedback_negative: int
    zero_result_queries: int


class StatsRates(ContractModel):
    zero_result_rate: float | None = None
    satisfaction_rate: float | None = Field(
        default=None, description="positive / (positive + negative); null without feedback"
    )
    degraded_rate: float | None = None


class StatsLatency(ContractModel):
    search_p50: int | None = None
    search_p95: int | None = None
    answer_ttft_p50: int | None = None
    answer_ttft_p95: int | None = None


class StatsDay(ContractModel):
    date: dt.date
    queries: int
    search_p95_ms: int | None = None
    zero_result_rate: float | None = None


class StatsLang(ContractModel):
    lang: Lang
    queries: int


class StatsMode(ContractModel):
    mode: SearchMode
    queries: int


class QueryCount(ContractModel):
    query: str = Field(description="Normalised query (lower-cased, whitespace-collapsed)")
    count: int


class StatsResponse(ContractModel):
    date_from: date
    date_to: date
    totals: StatsTotals
    rates: StatsRates
    latency_ms: StatsLatency
    by_day: list[StatsDay]
    by_lang: list[StatsLang]
    by_mode: list[StatsMode]
    top_queries: list[QueryCount] = Field(max_length=20)
    top_zero_result_queries: list[QueryCount] = Field(max_length=20)


# --- query log ---


class FeedbackCounts(ContractModel):
    positive: int
    negative: int


class QueryLogItem(ContractModel):
    query_id: UUID
    created_at: datetime
    query: str
    lang: Lang
    mode: SearchMode
    result_count: int
    top_article_id: str | None = None
    search_ms: int | None = None
    has_answer: bool
    feedback: FeedbackCounts
    degraded: list[Degraded] = Field(default_factory=list)


class QueryLogPage(PageMeta):
    items: list[QueryLogItem]


class QueryLogResult(ContractModel):
    rank: int
    article_id: str
    title: str | None = None
    doc_short_title: str | None = None
    score: float


class QueryLogAnswer(ContractModel):
    answer_id: UUID
    text: str
    citations: list[int]
    grounded: bool
    timing_ms: AnswerTiming


class FeedbackItem(ContractModel):
    target: FeedbackTarget
    article_id: str | None = None
    rating: Literal[1, -1]
    comment: str | None = None
    created_at: datetime


class QueryLogDetail(QueryLogItem):
    filters: SearchFilters
    top_k: int
    results: list[QueryLogResult]
    timing_ms: SearchTiming
    answer: QueryLogAnswer | None = None
    feedback_items: list[FeedbackItem]
    pipeline_version: str | None = None
    session_hash: str | None = None


# --- system, reindex, jobs ---

JobStatus = Literal["queued", "running", "succeeded", "failed"]


class Job(ContractModel):
    job_id: UUID
    kind: Literal["reindex"] = "reindex"
    status: JobStatus
    progress: float = Field(ge=0, le=1)
    message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PipelineInfo(ContractModel):
    pipeline_version: str | None = None
    embedder: str | None = None
    reranker: str | None = None
    generator: str | None = None
    index_compat_id: str | None = None


class IndexInfo(ContractModel):
    alias: str
    collection: str | None = None
    points: int | None = None
    documents: int | None = None
    articles: int | None = None
    index_compat_id: str | None = None
    compatible: bool = Field(
        description="Collection index_compat_id equals the manifest's; false = reindex required"
    )
    last_job: Job | None = None


class SystemResponse(ContractModel):
    components: Components
    app_version: str
    git_sha: str
    uptime_s: int
    pipeline: PipelineInfo
    index: IndexInfo


class ReindexRequest(ContractModel):
    source: Literal["processed", "sample"] = "processed"
    use_precomputed_embeddings: bool = True


class JobRef(ContractModel):
    job_id: UUID
