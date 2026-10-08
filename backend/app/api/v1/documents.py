from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.common import DocType, Lang
from app.schemas.documents import ArticleDetail, DocumentDetail, DocumentPage

router = APIRouter(tags=["documents"])


@router.get(
    "/documents",
    response_model=DocumentPage,
    summary="List documents",
    responses=errors(422, 501),
)
async def list_documents(
    lang: Annotated[Lang, Query()],
    doc_type: Annotated[DocType | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200, description="Substring of the title")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentPage:
    raise NotImplementedYet("GET /documents")


@router.get(
    "/documents/{doc_id}",
    response_model=DocumentDetail,
    summary="Document with its table of contents",
    responses=errors(404, 422, 501),
)
async def get_document(
    doc_id: Annotated[str, Path(max_length=64)],
    lang: Annotated[Lang, Query()],
) -> DocumentDetail:
    raise NotImplementedYet("GET /documents/{doc_id}")


@router.get(
    "/articles/{article_id}",
    response_model=ArticleDetail,
    summary="Full verbatim article",
    responses=errors(404, 422, 501),
    tags=["articles"],
)
async def get_article(article_id: Annotated[str, Path(max_length=128)]) -> ArticleDetail:
    raise NotImplementedYet("GET /articles/{article_id}")
