from fastapi import APIRouter

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.admin import SystemResponse

router = APIRouter()


@router.get(
    "/system",
    response_model=SystemResponse,
    summary="Components, pipeline and index status",
    responses=errors(401, 501),
)
async def system() -> SystemResponse:
    raise NotImplementedYet("GET /admin/system")
