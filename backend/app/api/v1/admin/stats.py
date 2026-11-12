from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminServiceDep
from app.api.responses import errors
from app.core.errors import APIError
from app.schemas.admin import StatsResponse

router = APIRouter()

DEFAULT_DAYS = 7
MAX_DAYS = 366


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Usage statistics (defaults to the last 7 days)",
    responses=errors(401, 422),
)
async def stats(
    service: AdminServiceDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> StatsResponse:
    """Days are UTC days; both bounds are inclusive."""
    last = date_to or datetime.now(UTC).date()
    first = date_from or last - timedelta(days=DEFAULT_DAYS - 1)
    if first > last:
        raise APIError(422, "date_from must not be after date_to")
    if (last - first).days >= MAX_DAYS:
        raise APIError(422, f"The range may span at most {MAX_DAYS} days")
    return await service.stats(first, last)
