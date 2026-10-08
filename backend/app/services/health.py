"""Component health for `GET /health` and the admin system page.

Overall status (contracts/api.md `/health`):
- `down` when the database is unreachable: not even the full-text fallback can work;
- `degraded` when Qdrant or the ML search models are not fully available;
- `ok` otherwise. The LLM is reported but does not affect the status: it only serves `/answer`.
"""

import asyncio
from collections.abc import Awaitable

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.schemas.common import ComponentStatus
from app.schemas.health import Components, HealthStatus
from app.schemas.ml import MlHealth
from app.services.ml_client import MlClient, MlUnavailable
from app.services.qdrant_store import QdrantStore

log = structlog.get_logger(__name__)

# ml-service components needed by /search; the generator only matters for /answer.
SEARCH_ML_COMPONENTS = ("embedder", "sparse", "reranker")


async def _probe(name: str, check: Awaitable[object], timeout_s: float) -> ComponentStatus:
    try:
        await asyncio.wait_for(check, timeout_s)
    except Exception as exc:  # any failure means the component is down
        log.warning("health_probe_failed", component=name, error=type(exc).__name__)
        return "down"
    return "ok"


def ml_statuses(health: MlHealth | None) -> tuple[ComponentStatus, ComponentStatus]:
    """(ml_service, llm) statuses from the ml-service /health body (None = unreachable)."""
    if health is None or health.status == "down":
        return "down", "unavailable"
    search_parts = [health.components.get(name, "ok") for name in SEARCH_ML_COMPONENTS]
    ml_status: ComponentStatus = "ok" if all(s == "ok" for s in search_parts) else "degraded"
    llm_status: ComponentStatus = (
        "ok" if health.components.get("generator", "unavailable") == "ok" else "unavailable"
    )
    return ml_status, llm_status


def overall_status(components: Components) -> HealthStatus:
    if components.database != "ok":
        return "down"
    if components.qdrant != "ok" or components.ml_service != "ok":
        return "degraded"
    return "ok"


class HealthService:
    def __init__(
        self, engine: AsyncEngine, qdrant: QdrantStore, ml: MlClient, timeout_s: float
    ) -> None:
        self._engine = engine
        self._qdrant = qdrant
        self._ml = ml
        self._timeout_s = timeout_s

    async def _ping_db(self) -> None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def _ml_health(self) -> MlHealth | None:
        try:
            return await self._ml.health(timeout_s=self._timeout_s)
        except MlUnavailable as exc:
            log.warning("health_probe_failed", component="ml_service", error=str(exc))
            return None

    async def components(self) -> Components:
        database, qdrant, ml_health = await asyncio.gather(
            _probe("database", self._ping_db(), self._timeout_s),
            _probe("qdrant", self._qdrant.ping(), self._timeout_s),
            self._ml_health(),
        )
        ml_service, llm = ml_statuses(ml_health)
        return Components(database=database, qdrant=qdrant, ml_service=ml_service, llm=llm)
