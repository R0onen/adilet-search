from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.admin import StatsResponse

router = APIRouter()


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Usage statistics (defaults to the last 7 days)",
    responses=errors(401, 422, 501),
)
async def stats(
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> StatsResponse:
    raise NotImplementedYet("GET /admin/stats")
