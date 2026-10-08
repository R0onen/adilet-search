from fastapi import APIRouter, Response

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.feedback import FeedbackRequest

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    status_code=204,
    response_class=Response,
    summary="Rate a result or an answer (a repeat overwrites)",
    responses=errors(404, 422, 501),
)
async def feedback(body: FeedbackRequest) -> Response:
    raise NotImplementedYet("POST /feedback")
