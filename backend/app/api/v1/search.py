from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.context import request_context
from app.api.deps import BackgroundDep, QueryLogDep, SearchServiceDep, SettingsDep, rate_limit
from app.api.responses import errors
from app.core import metrics
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
    _: Annotated[None, Depends(rate_limit("search"))],
) -> SearchResponse:
    ctx = request_context(request, settings.session_salt, "search")
    try:
        outcome = await service.search(body, ctx)
    except SearchError as exc:
        metrics.SEARCH_REQUESTS.labels(
            body.mode, str(exc.log_values.get("lang", "unknown")), "error"
        ).inc()
        background.spawn(query_log.write(exc.log_values))
        raise
    response = outcome.response
    metrics.observe_search(
        response.mode,
        response.lang,
        {stage: int(str(ms)) for stage, ms in response.timing_ms.items()},
        list(response.degraded),
        zero_results=not response.results,
    )
    background.spawn(query_log.write(outcome.log_values))
    return outcome.response
