"""Pydantic models for the internal ML service contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MlComponentStatus = Literal["ok", "degraded", "down", "unavailable"]


class OpenModel(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())


class EmbedderInfo(OpenModel):
    id: str
    dim: int
    distance: str = "cosine"
    max_seq_len: int | None = None
    query_prefix: str = ""
    passage_prefix: str = ""
    runtime: str | None = None


class SparseInfo(OpenModel):
    id: str
    type: str = "bm25"
    qdrant_idf_modifier: bool = True
    params: dict[str, float] = Field(default_factory=dict)


class RerankerInfo(OpenModel):
    id: str
    runtime: str | None = None


class GeneratorInfo(OpenModel):
    id: str
    served_model_name: str | None = None
    prompt_template: str | None = None
    max_context_tokens: int | None = None


class RetrievalParams(OpenModel):
    dense_limit: int = 50
    sparse_limit: int = 50
    rrf_k: int = 60
    weights: dict[str, float] = Field(default_factory=lambda: {"dense": 1.0, "sparse": 1.0})
    rerank_top_n: int = 30
    default_top_k: int = 10
    context_top_k: int = 5
    max_chars_per_context: int = 4000


class Manifest(OpenModel):
    pipeline_version: str
    created_at: str | None = None
    index_compat_id: str
    embedder: EmbedderInfo
    sparse: SparseInfo = Field(default_factory=lambda: SparseInfo(id="hash-bm25"))
    reranker: RerankerInfo = Field(default_factory=lambda: RerankerInfo(id="overlap"))
    generator: GeneratorInfo | None = None
    retrieval: RetrievalParams = Field(default_factory=RetrievalParams)
    corpus_version: str | None = None


class MlHealth(OpenModel):
    status: Literal["ok", "degraded", "down"]
    components: dict[str, MlComponentStatus]
    pipeline_version: str | None = None


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)
    kind: Literal["query", "passage"]
    return_dense: bool = True
    return_sparse: bool = True


class SparseVector(BaseModel):
    indices: list[int]
    values: list[float]


class EmbedResponse(OpenModel):
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


class RerankResponse(OpenModel):
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


class GenerateUsage(OpenModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GenerateDone(OpenModel):
    text: str
    finish_reason: str
    usage: GenerateUsage | None = None
    ttft_ms: int | None = None
    total_ms: int | None = None
    model_version: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
