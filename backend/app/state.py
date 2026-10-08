"""Process-wide resources, created in the app lifespan and stored on `app.state.resources`."""

import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.session import create_engine, create_sessionmaker
from app.services.health import HealthService
from app.services.manifest import ManifestProvider
from app.services.ml_client import MlClient
from app.services.qdrant_store import QdrantStore


@dataclass
class Resources:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    qdrant: QdrantStore
    ml: MlClient
    manifest: ManifestProvider
    health: HealthService
    started_at: float = field(default_factory=time.monotonic)

    @classmethod
    def create(cls, settings: Settings) -> "Resources":
        engine = create_engine(settings)
        qdrant = QdrantStore.from_url(
            settings.qdrant_url,
            settings.qdrant_alias,
            settings.qdrant_timeout_s,
            settings.qdrant_api_key,
        )
        ml = MlClient(settings.ml_service_url, settings.ml_timeout_s, settings.ml_connect_timeout_s)
        manifest = ManifestProvider(
            settings.manifest_source,
            Path(settings.model_manifest_path),
            ml,
            settings.manifest_retry_s,
        )
        health = HealthService(engine, qdrant, ml, settings.health_timeout_s)
        return cls(
            settings=settings,
            engine=engine,
            sessionmaker=create_sessionmaker(engine),
            qdrant=qdrant,
            ml=ml,
            manifest=manifest,
            health=health,
        )

    async def aclose(self) -> None:
        await self.ml.aclose()
        await self.qdrant.aclose()
        await self.engine.dispose()
