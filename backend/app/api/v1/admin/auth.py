from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, update

from app.api.deps import ResourcesDep, rate_limit
from app.api.responses import errors
from app.core.errors import APIError
from app.core.security import create_token, hash_password, verify_password
from app.db import repositories as repo
from app.db.models import AdminUser
from app.schemas.admin import LoginRequest, TokenResponse

router = APIRouter()

# Verified when the user does not exist, so both failures take the same time.
_DUMMY_HASH = hash_password("no-such-user")


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange admin credentials for a JWT",
    responses=errors(401, 422, 429),
)
async def login(
    body: LoginRequest,
    resources: ResourcesDep,
    _: Annotated[None, Depends(rate_limit("login"))],
) -> TokenResponse:
    settings = resources.settings
    async with resources.sessionmaker.begin() as session:
        user = await session.scalar(
            select(AdminUser).where(AdminUser.username == body.username, AdminUser.is_active)
        )
        valid = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
        if user is None or not valid:
            raise APIError(401, "Wrong username or password")
        await session.execute(
            update(AdminUser).where(AdminUser.id == user.id).values(last_login_at=repo.now_utc())
        )
    token = create_token(body.username, settings.jwt_secret, settings.jwt_ttl_s)
    return TokenResponse(access_token=token, expires_in=settings.jwt_ttl_s)
