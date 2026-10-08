"""Shared contract objects (contracts/api.md §1–2)."""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["ru", "kk"]
LangOrAuto = Literal["auto", "ru", "kk"]
SearchMode = Literal["hybrid", "semantic", "keyword"]
DocType = Literal["code", "law", "decree", "resolution", "order", "other"]
DocStatus = Literal["in_force", "repealed", "not_yet_in_force"]
UnitType = Literal["article", "paragraph", "chapter", "preamble", "annex"]
UnitStatus = Literal["in_force", "excluded"]
ScoreType = Literal["rerank", "fusion", "fts"]
Degraded = Literal["rerank", "semantic", "generation"]
ComponentStatus = Literal["ok", "degraded", "down", "unavailable"]

DOC_ID_EXAMPLE = "K1500000414"
ARTICLE_ID_EXAMPLE = "K1500000414:ru:a113"

ArticleId = Annotated[
    str,
    Field(
        min_length=5,
        max_length=128,
        pattern=r"^[A-Za-z0-9_]+:(ru|kk):[a-z0-9-]+$",
        description="`{doc_id}:{lang}:{unit_key}` (data_schema.md §2)",
        examples=[ARTICLE_ID_EXAMPLE],
    ),
]


class ContractModel(BaseModel):
    """Base for every contract object: examples go into the OpenAPI schema."""

    model_config = ConfigDict(populate_by_name=True)


class ErrorDetail(ContractModel):
    code: str = Field(description="Machine-readable error code, e.g. `validation_error`")
    message: str = Field(description="Human-readable message (English)")
    details: Any = Field(default=None, description="Extra data, e.g. per-field validation errors")
    request_id: str | None = Field(description="Same value as the `X-Request-Id` header")


class ErrorResponse(ContractModel):
    error: ErrorDetail


class DocumentRef(ContractModel):
    doc_id: str = Field(description="adilet document code", examples=[DOC_ID_EXAMPLE])
    title: str = Field(examples=["Трудовой кодекс Республики Казахстан"])
    short_title: str = Field(examples=["Трудовой кодекс РК"])
    doc_type: DocType
    number: str | None = Field(default=None, examples=["414-V"])
    adopted_date: date | None = Field(default=None, examples=["2015-11-23"])
    revision_date: date | None = Field(
        default=None, description="Date of the latest amendment in the text"
    )
    status: DocStatus
    url: str = Field(examples=["https://adilet.zan.kz/rus/docs/K1500000414"])


class ArticleRef(ContractModel):
    article_id: ArticleId
    unit_type: UnitType
    number: str | None = Field(default=None, examples=["113"])
    title: str | None = Field(
        default=None, examples=["Сроки, место и порядок выплаты заработной платы"]
    )
    section_title: str | None = None
    chapter_title: str | None = None
    unit_status: UnitStatus
    has_amendments: bool
    url: str = Field(description="Article anchor when known, otherwise the document URL")


class Highlight(ContractModel):
    start: int = Field(ge=0, description="Character offset into `snippet` (inclusive)")
    end: int = Field(ge=0, description="Character offset into `snippet` (exclusive)")


class SearchResult(ContractModel):
    rank: int = Field(ge=1)
    article: ArticleRef
    doc: DocumentRef
    chunk_id: str = Field(examples=["K1500000414:ru:a113:c0"])
    lang: Lang
    score: float
    score_type: ScoreType
    snippet: str = Field(max_length=300, description="Best passage of the best chunk")
    highlights: list[Highlight] = Field(default_factory=list)


class PageMeta(ContractModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
