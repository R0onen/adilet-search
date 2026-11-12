"""Process-wide resources, created in the app lifespan and stored on `app.state.resources`."""

import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.breaker import CircuitBreaker
from app.core.config import Settings
from app.core.ratelimit import RateLimiter
from app.db import repositories as repo
from app.db.models import Article, Document
from app.db.session import create_engine, create_sessionmaker
from app.services.admin import AdminService
from app.services.answer import AnswerConfig, AnswerService
from app.services.answer_store import AnswerStore
from app.services.background import BackgroundRunner
from app.services.feedback import FeedbackService
from app.services.fts_fallback import FtsFallback
from app.services.health import HealthService
from app.services.index_info import IndexInfoProvider
from app.services.manifest import ManifestProvider
from app.services.ml_client import MlClient
from app.services.qdrant_store import QdrantStore
from app.services.query_log import QueryLogWriter
from app.services.search import Resilience, SearchBudgets, SearchService


@dataclass
class Resources:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    qdrant: QdrantStore
    ml: MlClient
    manifest: ManifestProvider
    health: HealthService
    index_info: IndexInfoProvider
    search: SearchService
    answer: AnswerService
    feedback: FeedbackService
    query_log: QueryLogWriter
    background: BackgroundRunner
    admin: AdminService
    rate_limiter: RateLimiter
    started_at: float = field(default_factory=time.monotonic)

    @classmethod
    def create(cls, settings: Settings) -> "Resources":
        engine = create_engine(settings)
        sessionmaker = create_sessionmaker(engine)
        qdrant = QdrantStore.from_url(
            settings.qdrant_url,
            settings.qdrant_alias,
            settings.qdrant_timeout_s,
            settings.qdrant_api_key,
            prefer_grpc=settings.qdrant_prefer_grpc,
            grpc_port=settings.qdrant_grpc_port,
        )
        ml = MlClient(settings.ml_service_url, settings.ml_timeout_s, settings.ml_connect_timeout_s)
        manifest = ManifestProvider(
            settings.manifest_source,
            Path(settings.model_manifest_path),
            ml,
            settings.manifest_retry_s,
        )
        index_info = IndexInfoProvider(qdrant, sessionmaker, settings.index_state_ttl_s)

        def breaker(name: str) -> CircuitBreaker:
            return CircuitBreaker(name, settings.breaker_failures, settings.breaker_reset_s)

        async def lookup(article_ids: list[str]) -> dict[str, tuple[Article, Document]]:
            async with sessionmaker() as session:
                return await repo.fetch_articles(session, article_ids)

        search = SearchService(
            ml=ml,
            store=qdrant,
            lookup=lookup,
            manifest=manifest,
            index=index_info,
            budgets=SearchBudgets(
                embed_s=settings.search_embed_timeout_s,
                retrieve_s=settings.search_retrieve_timeout_s,
                rerank_s=settings.search_rerank_timeout_s,
                rerank_top_n=settings.search_rerank_top_n,
            ),
            resilience=Resilience(
                fts=FtsFallback(sessionmaker),
                ml_breaker=breaker("ml_embed"),
                rerank_breaker=breaker("ml_rerank"),
                store_breaker=breaker("qdrant"),
                cache_ttl_s=settings.cache_ttl_s,
                cache_size=settings.cache_size,
            ),
        )
        background = BackgroundRunner()
        answer = AnswerService(
            search=search,
            ml=ml,
            manifest=manifest,
            store=AnswerStore(sessionmaker),
            background=background,
            config=AnswerConfig(
                timeout_s=settings.answer_timeout_s,
                max_tokens=settings.answer_max_tokens,
                temperature=settings.answer_temperature,
            ),
        )
        return cls(
            settings=settings,
            engine=engine,
            sessionmaker=sessionmaker,
            qdrant=qdrant,
            ml=ml,
            manifest=manifest,
            health=HealthService(engine, qdrant, ml, settings.health_timeout_s),
            index_info=index_info,
            search=search,
            answer=answer,
            feedback=FeedbackService(sessionmaker),
            query_log=QueryLogWriter(sessionmaker),
            background=background,
            admin=AdminService(sessionmaker),
            rate_limiter=RateLimiter(),
        )

    async def aclose(self) -> None:
        await self.background.drain()
        await self.ml.aclose()
        await self.qdrant.aclose()
        await self.engine.dispose()
