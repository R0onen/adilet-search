from fastapi import APIRouter

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid / semantic / keyword search over articles",
    responses=errors(422, 429, 501, 503),
)
async def search(body: SearchRequest) -> SearchResponse:
    raise NotImplementedYet("POST /search")
