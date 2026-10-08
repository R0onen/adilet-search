from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.admin import QueryLogDetail, QueryLogPage
from app.schemas.common import Lang, SearchMode

router = APIRouter()

CSV_COLUMNS = (
    "query_id, created_at, query, lang, mode, result_count, top_article_id, search_ms, "
    "has_answer, feedback_positive, feedback_negative, degraded"
)


class QueryLogFilters(BaseModel):
    q: str | None = Field(default=None, max_length=200, description="Substring of the query")
    lang: Lang | None = None
    mode: SearchMode | None = None
    zero_results: bool | None = None
    feedback: Literal["positive", "negative"] | None = None
    degraded: bool | None = None
    date_from: date | None = None
    date_to: date | None = None


class QueryLogListParams(QueryLogFilters):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


@router.get(
    "/queries",
    response_model=QueryLogPage,
    summary="Query log (filtered, paginated)",
    responses=errors(401, 422, 501),
)
async def list_queries(params: Annotated[QueryLogListParams, Query()]) -> QueryLogPage:
    raise NotImplementedYet("GET /admin/queries")


@router.get(
    "/queries/export",
    response_class=Response,
    summary="Query log as CSV (UTF-8 with BOM)",
    responses={
        200: {
            "description": f"One row per query. Columns: {CSV_COLUMNS}",
            "content": {"text/csv": {"schema": {"type": "string"}}},
        },
        **errors(401, 422, 501),
    },
)
async def export_queries(params: Annotated[QueryLogFilters, Query()]) -> Response:
    raise NotImplementedYet("GET /admin/queries/export")


@router.get(
    "/queries/{query_id}",
    response_model=QueryLogDetail,
    summary="One query with results, answer and feedback",
    responses=errors(401, 404, 422, 501),
)
async def get_query(query_id: UUID) -> QueryLogDetail:
    raise NotImplementedYet("GET /admin/queries/{query_id}")
