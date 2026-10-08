from uuid import UUID

from fastapi import APIRouter

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.admin import Job, JobRef, ReindexRequest

router = APIRouter()


@router.post(
    "/reindex",
    status_code=202,
    response_model=JobRef,
    summary="Start a reindex job into a new collection",
    responses=errors(401, 409, 422, 501),
)
async def reindex(body: ReindexRequest) -> JobRef:
    raise NotImplementedYet("POST /admin/reindex")


@router.get(
    "/jobs/{job_id}",
    response_model=Job,
    summary="Job status and progress",
    responses=errors(401, 404, 422, 501),
)
async def get_job(job_id: UUID) -> Job:
    raise NotImplementedYet("GET /admin/jobs/{job_id}")
