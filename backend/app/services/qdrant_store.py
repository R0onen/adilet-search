"""Qdrant access: collection layout (contracts/data_schema.md §8), search, alias switching."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client import models as qm

DENSE = "dense"
SPARSE = "sparse"
KEYWORD_INDEXES = ("lang", "doc_id", "doc_type", "doc_status", "unit_status")
INTEGER_INDEXES = ("adopted_date",)
# Payload fields the search path needs back from Qdrant.
SEARCH_PAYLOAD = ["chunk_id", "article_id", "text", "text_for_embedding"]


@dataclass(frozen=True, slots=True)
class SearchFilter:
    lang: str
    doc_ids: Sequence[str] = ()
    doc_types: Sequence[str] = ()
    in_force_only: bool = True
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True, slots=True)
class Hit:
    chunk_id: str
    payload: dict[str, Any]


def date_to_int(value: date | None) -> int | None:
    """Payload stores `adopted_date` as an integer YYYYMMDD."""
    return value.year * 10000 + value.month * 100 + value.day if value else None


def build_filter(f: SearchFilter) -> qm.Filter:
    must: list[qm.Condition] = [qm.FieldCondition(key="lang", match=qm.MatchValue(value=f.lang))]
    if f.doc_ids:
        must.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=list(f.doc_ids))))
    if f.doc_types:
        must.append(qm.FieldCondition(key="doc_type", match=qm.MatchAny(any=list(f.doc_types))))
    if f.in_force_only:
        must.append(qm.FieldCondition(key="doc_status", match=qm.MatchValue(value="in_force")))
        must.append(qm.FieldCondition(key="unit_status", match=qm.MatchValue(value="in_force")))
    if f.date_from or f.date_to:
        must.append(
            qm.FieldCondition(
                key="adopted_date",
                range=qm.Range(gte=date_to_int(f.date_from), lte=date_to_int(f.date_to)),
            )
        )
    return qm.Filter(must=must)


class QdrantStore:
    def __init__(self, client: AsyncQdrantClient, alias: str) -> None:
        self.client = client
        self.alias = alias

    @classmethod
    def from_url(
        cls,
        url: str,
        alias: str,
        timeout_s: float,
        api_key: str | None = None,
        prefer_grpc: bool = True,
        grpc_port: int = 6334,
    ) -> "QdrantStore":
        client = AsyncQdrantClient(
            url=url,
            api_key=api_key,
            timeout=int(max(1, timeout_s)),
            prefer_grpc=prefer_grpc,
            grpc_port=grpc_port,
            check_compatibility=False,
        )
        return cls(client, alias)

    async def aclose(self) -> None:
        await self.client.close()

    async def ping(self) -> None:
        await self.client.get_collections()

    # --- aliases ------------------------------------------------------------------------------

    async def alias_target(self) -> str | None:
        """The collection the alias points to, or None if the alias does not exist yet."""
        response = await self.client.get_aliases()
        for alias in response.aliases:
            if alias.alias_name == self.alias:
                return alias.collection_name
        return None

    async def switch_alias(self, collection: str) -> str | None:
        """Atomically point the alias at `collection`. Returns the previous target."""
        previous = await self.alias_target()
        operations: list[qm.CreateAliasOperation | qm.DeleteAliasOperation] = []
        if previous is not None:
            operations.append(
                qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=self.alias))
            )
        operations.append(
            qm.CreateAliasOperation(
                create_alias=qm.CreateAlias(collection_name=collection, alias_name=self.alias)
            )
        )
        await self.client.update_collection_aliases(change_aliases_operations=operations)
        return previous

    # --- collections --------------------------------------------------------------------------

    async def collection_exists(self, name: str) -> bool:
        return await self.client.collection_exists(name)

    async def delete_collection(self, name: str) -> None:
        await self.client.delete_collection(name)

    async def create_collection(self, name: str, dim: int) -> None:
        await self.client.create_collection(
            collection_name=name,
            vectors_config={
                DENSE: qm.VectorParams(
                    size=dim,
                    distance=qm.Distance.COSINE,
                    hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=128),
                )
            },
            sparse_vectors_config={SPARSE: qm.SparseVectorParams(modifier=qm.Modifier.IDF)},
        )
        for field in KEYWORD_INDEXES:
            await self.client.create_payload_index(
                name, field, field_schema=qm.PayloadSchemaType.KEYWORD
            )
        for field in INTEGER_INDEXES:
            await self.client.create_payload_index(
                name, field, field_schema=qm.PayloadSchemaType.INTEGER
            )

    async def upsert(self, name: str, points: list[qm.PointStruct]) -> None:
        await self.client.upsert(collection_name=name, points=points, wait=True)

    async def count(self, name: str) -> int:
        return (await self.client.count(collection_name=name, exact=True)).count

    async def collection_dim(self, name: str) -> int | None:
        info = await self.client.get_collection(name)
        vectors = info.config.params.vectors
        if isinstance(vectors, dict) and DENSE in vectors:
            return vectors[DENSE].size
        return None

    # --- search -------------------------------------------------------------------------------

    async def _query(
        self, query: Any, using: str, query_filter: qm.Filter, limit: int
    ) -> list[Hit]:
        response = await self.client.query_points(
            collection_name=self.alias,
            query=query,
            using=using,
            query_filter=query_filter,
            limit=limit,
            with_payload=SEARCH_PAYLOAD,
        )
        hits = []
        for point in response.points:
            payload = dict(point.payload or {})
            hits.append(Hit(chunk_id=str(payload.get("chunk_id")), payload=payload))
        return hits

    async def search_dense(
        self, vector: list[float], query_filter: qm.Filter, limit: int
    ) -> list[Hit]:
        return await self._query(vector, DENSE, query_filter, limit)

    async def search_sparse(
        self, indices: list[int], values: list[float], query_filter: qm.Filter, limit: int
    ) -> list[Hit]:
        if not indices:
            return []
        vector = qm.SparseVector(indices=indices, values=values)
        return await self._query(vector, SPARSE, query_filter, limit)
