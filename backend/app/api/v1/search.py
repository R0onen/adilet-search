from fastapi import APIRouter, Request

from app.api.deps import BackgroundDep, QueryLogDep, SearchServiceDep, SettingsDep
from app.api.responses import errors
from app.schemas.search import SearchRequest, SearchResponse
from app.services.query_log import session_hash
from app.services.search import SearchContext, SearchError

router = APIRouter(tags=["search"])


def request_context(request: Request, salt: str, endpoint: str) -> SearchContext:
    session_id = request.headers.get("x-session-id")
    if request.headers.get("x-api-key"):
        client = "api-key"
    elif session_id:
        client = "web"
    else:
        client = "unknown"
    return SearchContext(
        session_hash=session_hash(session_id, salt), client=client, endpoint=endpoint
    )


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
