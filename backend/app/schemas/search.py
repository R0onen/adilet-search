"""`POST /search` (contracts/api.md §3)."""

import unicodedata
from datetime import date
from typing import TypedDict
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import (
    ContractModel,
    Degraded,
    DocType,
    Lang,
    LangOrAuto,
    SearchMode,
    SearchResult,
)

QUERY_MAX_CHARS = 500


class SearchFilters(ContractModel):
    doc_types: list[DocType] = Field(default_factory=list, description="Empty = no filter")
    doc_ids: list[str] = Field(
        default_factory=list, max_length=100, description="Empty = no filter"
    )
    in_force_only: bool = Field(
        default=True, description="Act in force **and** article not excluded"
    )
    date_from: date | None = Field(default=None, description="Act adoption date, inclusive")
    date_to: date | None = Field(default=None, description="Act adoption date, inclusive")

    @model_validator(mode="after")
    def _date_range(self) -> "SearchFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


class SearchRequest(ContractModel):
    query: str = Field(
        description="1–500 characters after trimming",
        examples=["Ответственность работодателя за задержку зарплаты"],
    )
    lang: LangOrAuto = Field(
        default="auto",
        description="`auto`: `kk` if the query contains any of ә ғ қ ң ө ұ ү һ і, otherwise `ru`",
    )
    mode: SearchMode = "hybrid"
    top_k: int = Field(default=10, ge=1, le=50)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("query")
    @classmethod
    def _normalise_query(cls, value: str) -> str:
        value = unicodedata.normalize("NFC", value).strip()
        if not 1 <= len(value) <= QUERY_MAX_CHARS:
            raise ValueError(f"Query must be 1–{QUERY_MAX_CHARS} characters")
        return value


class SearchTiming(TypedDict, total=False):
    """Milliseconds per stage. A key is present only if its stage ran."""

    embed: int
    retrieve: int
    fuse: int
    rerank: int
    total: int


class SearchResponse(ContractModel):
    query_id: UUID
    query: str
    lang: Lang = Field(description="The resolved language")
    mode: SearchMode
    results: list[SearchResult] = Field(description="One result per article; may be empty")
    total_candidates: int = Field(ge=0)
    degraded: list[Degraded] = Field(default_factory=list)
    timing_ms: SearchTiming
    pipeline_version: str | None = None
