"""Documents and articles (contracts/api.md §3)."""

from pydantic import Field

from app.schemas.common import (
    ArticleId,
    ArticleRef,
    ContractModel,
    DocumentRef,
    Lang,
    PageMeta,
    UnitStatus,
    UnitType,
)


class DocumentListItem(DocumentRef):
    article_count: int = Field(ge=0)


class DocumentPage(PageMeta):
    items: list[DocumentListItem]


class TocItem(ContractModel):
    article_id: ArticleId
    unit_type: UnitType
    number: str | None = None
    title: str | None = None
    section_title: str | None = None
    chapter_title: str | None = None
    unit_status: UnitStatus


class DocumentDetail(DocumentRef):
    toc: list[TocItem] = Field(description="Units in document order")


class ArticleDetail(ContractModel):
    article: ArticleRef
    doc: DocumentRef
    lang: Lang
    text: str = Field(description="Full verbatim article text; line breaks and numbering preserved")
    amendment_notes: list[str] = Field(default_factory=list)
    parallel_article_id: str | None = Field(
        default=None, description="The same unit in the other language"
    )
    prev_article_id: str | None = None
    next_article_id: str | None = None
