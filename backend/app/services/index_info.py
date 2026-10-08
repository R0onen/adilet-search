"""Which collection serves search, and is it compatible with the loaded manifest?

The alias target and its `index_state` row are cached for `INDEX_STATE_TTL_S`, so the search path
does not hit Qdrant and Postgres for this on every request. A reindex calls `invalidate()`.
"""

import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import repositories as repo
from app.services.qdrant_store import QdrantStore


@dataclass(frozen=True, slots=True)
class ActiveIndex:
    collection: str | None
    index_compat_id: str | None
    pipeline_version: str | None

    def compatible_with(self, index_compat_id: str) -> bool:
        return self.collection is not None and self.index_compat_id == index_compat_id


class IndexInfoProvider:
    def __init__(
        self,
        store: QdrantStore,
        sessionmaker: async_sessionmaker[AsyncSession],
        ttl_s: float,
    ) -> None:
        self._store = store
        self._sessions = sessionmaker
        self._ttl_s = ttl_s
        self._cached: ActiveIndex | None = None
        self._loaded_at = float("-inf")

    def invalidate(self) -> None:
        self._cached = None

    async def get(self) -> ActiveIndex:
        """Raises if Qdrant or Postgres is unreachable (the caller decides how to degrade)."""
        if self._cached is not None and time.monotonic() - self._loaded_at < self._ttl_s:
            return self._cached
        collection = await self._store.alias_target()
        state = None
        if collection is not None:
            async with self._sessions() as session:
                state = await repo.get_index_state(session, collection)
        self._cached = ActiveIndex(
            collection=collection,
            index_compat_id=state.index_compat_id if state else None,
            pipeline_version=state.pipeline_version if state else None,
        )
        self._loaded_at = time.monotonic()
        return self._cached
