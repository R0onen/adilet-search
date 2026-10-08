"""`GET /health` and `GET /version` (contracts/api.md §3)."""

from typing import Literal

from pydantic import Field

from app.schemas.common import ComponentStatus, ContractModel

HealthStatus = Literal["ok", "degraded", "down"]


class Components(ContractModel):
    database: ComponentStatus
    qdrant: ComponentStatus
    ml_service: ComponentStatus
    llm: ComponentStatus


class HealthResponse(ContractModel):
    status: HealthStatus = Field(
        description="`ok` (200), `degraded`: search works but a component is down (200), "
        "`down`: search cannot work (503)"
    )
    components: Components
    pipeline_version: str | None = None
    app_version: str


class VersionResponse(ContractModel):
    app_version: str
    git_sha: str
    pipeline_version: str | None = None
    index_collection: str | None = Field(
        default=None, description="The collection the `legal_chunks` alias points to"
    )
