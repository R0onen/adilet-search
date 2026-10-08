from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.api.responses import errors
from app.core.errors import APIError
from app.db import repositories as repo
from app.schemas.common import DocType, Lang
from app.schemas.documents import (
    ArticleDetail,
    DocumentDetail,
    DocumentListItem,
    DocumentPage,
    TocItem,
)
from app.services.mappers import article_ref, document_ref

router = APIRouter(tags=["documents"])


@router.get(
    "/documents",
    response_model=DocumentPage,
    summary="List documents",
    responses=errors(422),
)
async def list_documents(
    session: SessionDep,
    lang: Annotated[Lang, Query()],
    doc_type: Annotated[DocType | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200, description="Substring of the title")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentPage:
    documents, total = await repo.list_documents(session, lang, doc_type, q, page, page_size)
    return DocumentPage(
        items=[
            DocumentListItem(**document_ref(d).model_dump(), article_count=d.article_count)
            for d in documents
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/documents/{doc_id}",
    response_model=DocumentDetail,
    summary="Document with its table of contents",
    responses=errors(404, 422),
)
async def get_document(
    session: SessionDep,
    doc_id: Annotated[str, Path(max_length=64)],
    lang: Annotated[Lang, Query()],
) -> DocumentDetail:
    document = await repo.get_document(session, doc_id, lang)
    if document is None:
        raise APIError(404, f"Document {doc_id} ({lang}) not found")
    toc = await repo.document_toc(session, doc_id, lang)
    return DocumentDetail(
        **document_ref(document).model_dump(),
        toc=[
            TocItem(
                article_id=a.article_id,
                unit_type=a.unit_type,
                number=a.unit_number,
                title=a.unit_title,
                section_title=a.section_title,
                chapter_title=a.chapter_title,
                unit_status=a.unit_status,
            )
            for a in toc
        ],
    )


@router.get(
    "/articles/{article_id}",
    response_model=ArticleDetail,
    summary="Full verbatim article",
    responses=errors(404, 422),
    tags=["articles"],
)
async def get_article(
    session: SessionDep, article_id: Annotated[str, Path(max_length=128)]
) -> ArticleDetail:
    found = await repo.get_article(session, article_id)
    if found is None:
        raise APIError(404, f"Article {article_id} not found")
    article, document = found
    prev_id, next_id = await repo.neighbour_ids(session, article)
    return ArticleDetail(
        article=article_ref(article),
        doc=document_ref(document),
        lang=article.lang,
        text=article.text,
        amendment_notes=list(article.amendment_notes),
        parallel_article_id=article.parallel_article_id,
        prev_article_id=prev_id,
        next_article_id=next_id,
    )
