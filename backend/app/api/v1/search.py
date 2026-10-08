from fastapi import APIRouter, Request

from app.api.context import request_context
from app.api.deps import BackgroundDep, QueryLogDep, SearchServiceDep, SettingsDep
from app.api.responses import errors
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search import SearchError

router = APIRouter(tags=["search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid / semantic / keyword search over articles",
    responses=errors(422, 429, 503),
)
async def search(
    body: SearchRequest,
    request: Request,
    service: SearchServiceDep,
    query_log: QueryLogDep,
    background: BackgroundDep,
    settings: SettingsDep,
) -> SearchResponse:
    ctx = request_context(request, settings.session_salt, "search")
    try:
        outcome = await service.search(body, ctx)
    except SearchError as exc:
        background.spawn(query_log.write(exc.log_values))
        raise
    background.spawn(query_log.write(outcome.log_values))
    return outcome.response
