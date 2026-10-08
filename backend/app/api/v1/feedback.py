from fastapi import APIRouter, Request, Response

from app.api.deps import FeedbackServiceDep, SettingsDep
from app.api.responses import errors
from app.schemas.feedback import FeedbackRequest
from app.services.query_log import session_hash

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    status_code=204,
    response_class=Response,
    summary="Rate a result or an answer (a repeat overwrites)",
    responses=errors(404, 422),
)
async def feedback(
    body: FeedbackRequest, request: Request, service: FeedbackServiceDep, settings: SettingsDep
) -> Response:
    await service.submit(
        body, session_hash(request.headers.get("x-session-id"), settings.session_salt)
    )
    return Response(status_code=204)
