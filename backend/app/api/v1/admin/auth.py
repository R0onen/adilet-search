from fastapi import APIRouter

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.admin import LoginRequest, TokenResponse

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange admin credentials for a JWT",
    responses=errors(401, 422, 429, 501),
)
async def login(body: LoginRequest) -> TokenResponse:
    raise NotImplementedYet("POST /admin/login")
