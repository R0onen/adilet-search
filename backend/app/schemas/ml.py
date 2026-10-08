"""Internal ML service contract (contracts/ml_service.md). Not part of the public OpenAPI.

Models accept extra fields, so the ML agent can add manifest keys without breaking the backend.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MlComponentStatus = Literal["ok", "degraded", "down", "unavailable"]


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())


# --- manifest (ml_service.md §3) ---


class EmbedderInfo(_Open):
    id: str
    dim: int
    distance: str = "cosine"
    max_seq_len: int | None = None


class SparseInfo(_Open):
    id: str
    type: str = "bm25"
    qdrant_idf_modifier: bool = True


class RerankerInfo(_Open):
    id: str


class GeneratorInfo(_Open):
    id: str
    served_model_name: str | None = None
    prompt_template: str | None = None


class RetrievalParams(_Open):
    dense_limit: int = 50
    sparse_limit: int = 50
    rrf_k: int = 60
    weights: dict[str, float] = Field(default_factory=lambda: {"dense": 1.0, "sparse": 1.0})
    rerank_top_n: int = 30
    default_top_k: int = 10
    context_top_k: int = 5
    max_chars_per_context: int = 4000


class Manifest(_Open):
    pipeline_version: str
    index_compat_id: str
    embedder: EmbedderInfo
    sparse: SparseInfo | None = None
    reranker: RerankerInfo | None = None
    generator: GeneratorInfo | None = None
    retrieval: RetrievalParams = Field(default_factory=RetrievalParams)
    corpus_version: str | None = None


# --- endpoints (ml_service.md §1) ---


class MlHealth(_Open):
    status: Literal["ok", "degraded", "down"]
    components: dict[str, MlComponentStatus] = Field(default_factory=dict)
    pipeline_version: str | None = None


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)
    kind: Literal["query", "passage"]
    return_dense: bool = True
    return_sparse: bool = True


class SparseVector(BaseModel):
    indices: list[int]
    values: list[float]


class EmbedResponse(_Open):
    dense: list[list[float]] | None
    sparse: list[SparseVector] | None
    dim: int
    truncated: list[bool]
    model_version: str


class RerankCandidate(BaseModel):
    id: str
    text: str


class RerankRequest(BaseModel):
    query: str
    candidates: list[RerankCandidate] = Field(max_length=100)
    top_n: int | None = None


class RerankScore(BaseModel):
    id: str
    score: float


class RerankResponse(_Open):
    results: list[RerankScore]
    model_version: str


class GenerateSource(BaseModel):
    ref: int = Field(ge=1)
    article_id: str
    title: str
    text: str


class GenerateRequest(BaseModel):
    question: str
    lang: Literal["ru", "kk"]
    sources: list[GenerateSource] = Field(max_length=8)
    max_tokens: int = Field(default=512, ge=1, le=1024)
    temperature: float = 0.1
    stream: bool = True


class GenerateUsage(_Open):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GenerateDone(_Open):
    text: str
    finish_reason: str
    usage: GenerateUsage | None = None
    ttft_ms: int | None = None
    total_ms: int | None = None
    model_version: str
