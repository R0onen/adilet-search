"""The indexing pipeline, shared by the CLI and (BE-04) the admin reindex job.

Order: validate Parquet → upsert Postgres → build a NEW collection → verify the point count →
record index_state → switch the alias atomically → prune rows that left the corpus.
The alias moves only after the new collection is complete, so the old index keeps serving if
anything fails, and the previous collection stays available for rollback.
"""

import asyncio
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import structlog
from qdrant_client import models as qm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import repositories as repo
from app.schemas.ml import Manifest
from app.services.ml_client import MlClient, MlUnavailable
from app.services.qdrant_store import QdrantStore, date_to_int
from indexer.corpus import Corpus, load_corpus

log = structlog.get_logger(__name__)

EMBED_RETRIES = 3
UPSERT_BATCH = 256


class JobConflict(Exception):
    """Another index job is queued or running."""


class IndexingError(Exception):
    pass


@dataclass
class IndexOptions:
    data_dir: Path
    embeddings: Path | None = None
    batch_size: int = 64
    switch_alias: bool = True
    prune: bool = True


@dataclass
class IndexResult:
    job_id: uuid.UUID
    collection: str
    previous_collection: str | None
    switched: bool
    points: int
    documents: int
    articles: int
    pg_documents: repo.UpsertCounts
    pg_articles: repo.UpsertCounts
    duration_s: float
    timings_s: dict[str, float] = field(default_factory=dict)


def point_id(chunk_id: str) -> str:
    """Qdrant point id = uuid5(NAMESPACE_URL, chunk_id) (data_schema.md §2)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def chunk_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    """Payload fields of data_schema.md §8."""
    return {
        "chunk_id": chunk["chunk_id"],
        "article_id": chunk["article_id"],
        "doc_id": chunk["doc_id"],
        "lang": chunk["lang"],
        "doc_type": chunk["doc_type"],
        "doc_status": chunk["doc_status"],
        "unit_status": chunk["unit_status"],
        "adopted_date": date_to_int(chunk["adopted_date"]),
        "unit_number": chunk["unit_number"],
        "unit_title": chunk["unit_title"],
        "doc_short_title": chunk["doc_short_title"],
        "text": chunk["text"],
        "text_for_embedding": chunk["text_for_embedding"],
        "source_url": chunk["source_url"],
    }


@dataclass
class Vectors:
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


def load_precomputed(
    path: Path, manifest: Manifest, chunk_ids: Sequence[str]
) -> dict[str, Vectors]:
    """Read `embeddings_{pipeline_version}.parquet` (data_schema.md §1) and check it fits."""
    table = pq.read_table(path)
    metadata = {k.decode(): v.decode() for k, v in (table.schema.metadata or {}).items()}
    version = metadata.get("pipeline_version")
    if version is None and path.stem.startswith("embeddings_"):
        version = path.stem.removeprefix("embeddings_")
    if version != manifest.pipeline_version:
        raise IndexingError(
            f"{path.name} is for pipeline_version {version!r}, "
            f"the manifest is {manifest.pipeline_version!r}"
        )
    needed = {"chunk_id", "dense", "sparse_indices", "sparse_values"}
    if missing := needed - set(table.schema.names):
        raise IndexingError(f"{path.name}: missing columns {sorted(missing)}")
    vectors = {}
    for row in table.select(sorted(needed)).to_pylist():
        if len(row["dense"]) != manifest.embedder.dim:
            raise IndexingError(
                f"{path.name}: {row['chunk_id']} has dim {len(row['dense'])}, "
                f"expected {manifest.embedder.dim}"
            )
        vectors[row["chunk_id"]] = Vectors(
            row["dense"], list(row["sparse_indices"]), list(row["sparse_values"])
        )
    if missing_chunks := [c for c in chunk_ids if c not in vectors]:
        raise IndexingError(
            f"{path.name}: no vectors for {len(missing_chunks)} chunks, e.g. {missing_chunks[:3]}"
        )
    return vectors


class Indexer:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        store: QdrantStore,
        ml: MlClient,
        manifest: Manifest,
        embed_timeout_s: float = 120.0,
    ) -> None:
        self._sessions = sessionmaker
        self._store = store
        self._ml = ml
        self._manifest = manifest
        self._embed_timeout_s = embed_timeout_s

    # --- job bookkeeping ----------------------------------------------------------------------

    async def create_job(self, params: dict[str, Any]) -> uuid.UUID:
        try:
            async with self._sessions.begin() as session:
                return await repo.create_job(session, params)
        except IntegrityError as exc:
            raise JobConflict("another index job is queued or running") from exc

    async def abandon_stuck_jobs(self) -> list[uuid.UUID]:
        """Fail queued/running jobs and delete their unfinished collections.

        For a job whose process died (crash, killed container, Docker restart) and so never reached
        its own failure handler; it would otherwise block every later run. The database cannot tell
        a dead job from a live one, so call this only when no indexer is running.
        """
        async with self._sessions.begin() as session:
            abandoned = await repo.abandon_active_jobs(
                session, "abandoned: the indexer process stopped without finishing this job"
            )
        for job_id, collection in abandoned:
            log.warning("index_job_abandoned", job_id=str(job_id), collection=collection)
            if (
                collection is not None
                and await self._safe_is_unused(collection)
                and await self._store.collection_exists(collection)
            ):
                await self._store.delete_collection(collection)
        return [job_id for job_id, _ in abandoned]

    async def _job(self, job_id: uuid.UUID, **values: Any) -> None:
        async with self._sessions.begin() as session:
            await repo.update_job(session, job_id, **values)

    async def _progress(self, job_id: uuid.UUID, progress: float, message: str) -> None:
        log.info("index_progress", job_id=str(job_id), progress=round(progress, 3), message=message)
        await self._job(job_id, progress=min(max(progress, 0.0), 1.0), message=message)

    # --- steps ----------------------------------------------------------------------------------

    async def _collection_name(self) -> str:
        """`{alias}__{pipeline_version}`, or a timestamped sibling if that name is taken.

        Existing collections are never deleted here: one serves search, the others are kept for
        rollback (a failed build deletes its own collection).
        """
        base = f"{self._store.alias}__{self._manifest.pipeline_version}"
        if not await self._store.collection_exists(base):
            return base
        stamped = f"{base}__{datetime.now(UTC):%Y%m%d%H%M%S}"
        name, n = stamped, 1
        while await self._store.collection_exists(name):
            n += 1
            name = f"{stamped}-{n}"
        return name

    async def _embed_batch(self, texts: list[str]) -> list[Vectors]:
        for attempt in range(1, EMBED_RETRIES + 1):
            try:
                response = await self._ml.embed(texts, "passage", timeout_s=self._embed_timeout_s)
                break
            except MlUnavailable as exc:
                if attempt == EMBED_RETRIES:
                    raise IndexingError(f"/embed failed {attempt} times: {exc}") from exc
                log.warning("embed_retry", attempt=attempt, error=str(exc))
                await asyncio.sleep(2 ** (attempt - 1))
        if response.dense is None or response.sparse is None:
            raise IndexingError("/embed returned no vectors")
        if response.dim != self._manifest.embedder.dim:
            raise IndexingError(
                f"/embed returned dim {response.dim}, manifest says {self._manifest.embedder.dim}"
            )
        return [
            Vectors(dense, sparse.indices, sparse.values)
            for dense, sparse in zip(response.dense, response.sparse, strict=True)
        ]

    async def _build_points(
        self, job_id: uuid.UUID, collection: str, corpus: Corpus, options: IndexOptions
    ) -> None:
        chunks = corpus.chunks
        precomputed = (
            load_precomputed(options.embeddings, self._manifest, [c["chunk_id"] for c in chunks])
            if options.embeddings
            else None
        )
        batch_size = options.batch_size if precomputed is None else UPSERT_BATCH
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            if precomputed is not None:
                vectors = [precomputed[c["chunk_id"]] for c in batch]
            else:
                vectors = await self._embed_batch([c["text_for_embedding"] for c in batch])
            points = [
                qm.PointStruct(
                    id=point_id(chunk["chunk_id"]),
                    vector={
                        "dense": vec.dense,
                        "sparse": qm.SparseVector(
                            indices=vec.sparse_indices, values=vec.sparse_values
                        ),
                    },
                    payload=chunk_payload(chunk),
                )
                for chunk, vec in zip(batch, vectors, strict=True)
            ]
            await self._store.upsert(collection, points)
            done = start + len(batch)
            verb = "loaded" if precomputed is not None else "embedded"
            await self._progress(
                job_id, 0.2 + 0.7 * done / len(chunks), f"{verb} {done}/{len(chunks)} chunks"
            )

    # --- the whole run ----------------------------------------------------------------------------

    async def run(self, options: IndexOptions, job_id: uuid.UUID | None = None) -> IndexResult:
        if job_id is None:
            job_id = await self.create_job(
                {
                    "data_dir": str(options.data_dir),
                    "embeddings": str(options.embeddings) if options.embeddings else None,
                    "switch_alias": options.switch_alias,
                }
            )
        started = time.perf_counter()
        timings: dict[str, float] = {}
        collection: str | None = None
        await self._job(job_id, status="running", started_at=repo.now_utc(), progress=0.0)
        try:
            t = time.perf_counter()
            corpus = load_corpus(options.data_dir)
            timings["validate"] = time.perf_counter() - t
            await self._progress(
                job_id,
                0.05,
                f"validated {len(corpus.documents)} documents, {len(corpus.articles)} articles, "
                f"{len(corpus.chunks)} chunks",
            )

            t = time.perf_counter()
            # articles.parquet has no corpus_version (data_schema.md §4): take the document's.
            doc_versions = {(d["doc_id"], d["lang"]): d["corpus_version"] for d in corpus.documents}
            article_rows = [
                {**a, "corpus_version": doc_versions[(a["doc_id"], a["lang"])]}
                for a in corpus.articles
            ]
            async with self._sessions.begin() as session:
                pg_docs = await repo.upsert_documents(session, corpus.documents)
                pg_articles = await repo.upsert_articles(session, article_rows)
            timings["postgres"] = time.perf_counter() - t
            await self._progress(
                job_id,
                0.15,
                f"postgres: documents {pg_docs}, articles {pg_articles}",
            )

            t = time.perf_counter()
            collection = await self._collection_name()
            await self._store.create_collection(collection, self._manifest.embedder.dim)
            await self._job(job_id, collection=collection)
            await self._build_points(job_id, collection, corpus, options)
            timings["vectors"] = time.perf_counter() - t

            points = await self._store.count(collection)
            if points != len(corpus.chunks):
                raise IndexingError(
                    f"{collection} has {points} points, expected {len(corpus.chunks)} chunks"
                )
            async with self._sessions.begin() as session:
                await repo.record_index_state(
                    session,
                    {
                        "collection": collection,
                        "pipeline_version": self._manifest.pipeline_version,
                        "index_compat_id": self._manifest.index_compat_id,
                        "corpus_version": corpus.corpus_version,
                        "points_count": points,
                        "documents_count": len(corpus.documents),
                        "articles_count": len(corpus.articles),
                        "job_id": job_id,
                    },
                )

            previous = await self._store.alias_target()
            if options.switch_alias:
                previous = await self._store.switch_alias(collection)
                if options.prune:
                    async with self._sessions.begin() as session:
                        pruned = await repo.prune_corpus(
                            session,
                            [(d["doc_id"], d["lang"]) for d in corpus.documents],
                            [a["article_id"] for a in corpus.articles],
                        )
                    log.info("pruned", documents=pruned[0], articles=pruned[1])

            duration = time.perf_counter() - started
            switched = "alias switched" if options.switch_alias else "alias NOT switched"
            await self._job(
                job_id,
                status="succeeded",
                progress=1.0,
                finished_at=repo.now_utc(),
                message=f"{points} points in {collection}; {switched}; {duration:.1f}s",
            )
            return IndexResult(
                job_id=job_id,
                collection=collection,
                previous_collection=previous,
                switched=options.switch_alias,
                points=points,
                documents=len(corpus.documents),
                articles=len(corpus.articles),
                pg_documents=pg_docs,
                pg_articles=pg_articles,
                duration_s=duration,
                timings_s=timings,
            )
        except BaseException as exc:
            log.exception("index_failed", job_id=str(job_id), collection=collection)
            if collection is not None and await self._safe_is_unused(collection):
                await self._store.delete_collection(collection)
            await self._job(
                job_id,
                status="failed",
                finished_at=repo.now_utc(),
                error=str(exc)[:4000],
                message=f"failed: {type(exc).__name__}",
            )
            raise

    async def _safe_is_unused(self, collection: str) -> bool:
        try:
            return await self._store.alias_target() != collection
        except Exception:
            return False
