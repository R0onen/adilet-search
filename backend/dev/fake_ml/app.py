"""Fake ML service that obeys contracts/ml_service.md. For development and tests only.

Run: `uv run uvicorn dev.fake_ml.app:app --port 8001`

- `/embed`: deterministic hash-based vectors. A dense vector is the normalised sum of per-token
  pseudo-random vectors, so texts that share words are close (search results look plausible).
  The sparse vector holds lowercase tokens hashed to uint32, weight 1.0.
- `/rerank`: token-overlap score.
- `/generate`: streams a canned answer citing `[1]`, token by token.

Env:
- `FAKE_ML_DIM` (768): dense dimension.
- `FAKE_ML_FAIL` (empty): comma list of `embed`, `rerank`, `generate` or `all`; those endpoints
  fail (503, or an SSE `error` event for streaming generate).
- `FAKE_ML_LATENCY_MS` (0): extra delay on embed/rerank and before the first generated token.
- `FAKE_ML_TOKEN_DELAY_MS` (20): delay between streamed tokens.
"""

import asyncio
import hashlib
import json
import math
import os
import re
import time
import uuid
import zlib
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import numpy as np
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from app.schemas.ml import (
    EmbedRequest,
    EmbedResponse,
    GenerateDone,
    GenerateRequest,
    GenerateUsage,
    RerankRequest,
    RerankResponse,
    RerankScore,
    SparseVector,
)

MODEL_VERSION = "0.0.0-fake"
INDEX_COMPAT_ID = "fake"
MAX_TEXT_CHARS = 8000
MAX_SEQ_TOKENS = 512
TOKEN_RE = re.compile(r"\w+", re.UNICODE)

CANNED_ANSWER = {
    "ru": "Согласно приведённой норме, ответ на вопрос содержится в источнике [1]. "
    "Это тестовый ответ фиктивного ML-сервиса.",
    "kk": "Келтірілген нормаға сәйкес, сұраққа жауап [1] дереккөзде берілген. "
    "Бұл жалған ML-сервистің сынақ жауабы.",
}


def _dim() -> int:
    return int(os.getenv("FAKE_ML_DIM", "768"))


def _failing() -> set[str]:
    raw = os.getenv("FAKE_ML_FAIL", "")
    parts = {part.strip() for part in raw.split(",") if part.strip()}
    return {"embed", "rerank", "generate"} if "all" in parts else parts


def _latency_s() -> float:
    return int(os.getenv("FAKE_ML_LATENCY_MS", "0")) / 1000


def _token_delay_s() -> float:
    return int(os.getenv("FAKE_ML_TOKEN_DELAY_MS", "20")) / 1000


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def sparse_index(token: str) -> int:
    return zlib.crc32(token.encode("utf-8")) & 0xFFFFFFFF


@lru_cache(maxsize=50_000)
def _token_vector(token: str, dim: int) -> np.ndarray:
    seed = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "little")
    return np.random.default_rng(seed).standard_normal(dim).astype(np.float32)


def dense_vector(tokens: list[str], dim: int) -> list[float]:
    vec = np.zeros(dim, dtype=np.float32)
    for token in tokens:
        vec += _token_vector(token, dim)
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        # Empty text: a fixed unit vector keeps the output L2-normalised.
        vec[0] = 1.0
        norm = 1.0
    result: list[float] = (vec / norm).tolist()
    return result


def sparse_vector(tokens: list[str]) -> SparseVector:
    indices = sorted({sparse_index(token) for token in tokens})
    return SparseVector(indices=indices, values=[1.0] * len(indices))


def overlap_score(query: str, text: str) -> float:
    q = set(tokenize(query))
    t = tokenize(text)
    if not q or not t:
        return 0.0
    hits = sum(1 for token in set(t) if token in q)
    return round(hits / math.sqrt(len(set(t))) + hits, 6)


def fake_manifest() -> dict[str, Any]:
    dim = _dim()
    return {
        "pipeline_version": MODEL_VERSION,
        "created_at": "2026-10-08",
        "index_compat_id": INDEX_COMPAT_ID,
        "embedder": {
            "id": "fake-hash-embedder",
            "hf_repo": None,
            "revision": None,
            "dim": dim,
            "distance": "cosine",
            "max_seq_len": MAX_SEQ_TOKENS,
            "query_prefix": "",
            "passage_prefix": "",
            "runtime": "numpy",
        },
        "sparse": {
            "id": "fake-token-hash",
            "type": "bm25",
            "qdrant_idf_modifier": True,
            "params": {},
        },
        "reranker": {"id": "fake-overlap", "hf_repo": None, "revision": None, "runtime": "python"},
        "generator": {
            "id": "fake-canned",
            "base_model": None,
            "adapter": None,
            "gguf": None,
            "served_model_name": "fake",
            "prompt_template": None,
            "max_context_tokens": 6000,
        },
        "retrieval": {
            "dense_limit": 50,
            "sparse_limit": 50,
            "rrf_k": 60,
            "weights": {"dense": 1.0, "sparse": 1.0},
            "rerank_top_n": 30,
            "default_top_k": 10,
            "context_top_k": 5,
            "max_chars_per_context": 4000,
        },
        "chunking": {"version": "ch1", "max_chunk_tokens": 400, "tokenizer": "whitespace"},
        "corpus_version": None,
        "eval": {"dataset": None, "ndcg@10": None, "recall@10": None, "mrr@10": None},
    }


def _error(status: int, code: str, message: str, request: Request) -> JSONResponse:
    request_id = request.headers.get("x-request-id")
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": None, "request_id": request_id}
        },
    )


app = FastAPI(title="Fake ML service", version=MODEL_VERSION)
_requests_total: dict[tuple[str, str], int] = {}


@app.middleware("http")
async def _request_id_and_metrics(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    key = (request.url.path, str(response.status_code))
    _requests_total[key] = _requests_total.get(key, 0) + 1
    return response


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error(422, "validation_error", str(exc.errors()[0].get("msg", "invalid")), request)


@app.get("/health")
async def health() -> JSONResponse:
    failing = _failing()
    components = {
        "embedder": "down" if "embed" in failing else "ok",
        "sparse": "down" if "embed" in failing else "ok",
        "reranker": "down" if "rerank" in failing else "ok",
        "generator": "unavailable" if "generate" in failing else "ok",
    }
    if components["embedder"] == "down":
        status = "down"
    elif any(value != "ok" for value in components.values()):
        status = "degraded"
    else:
        status = "ok"
    return JSONResponse(
        status_code=503 if status == "down" else 200,
        content={"status": status, "components": components, "pipeline_version": MODEL_VERSION},
    )


@app.get("/version")
async def version() -> dict[str, Any]:
    return fake_manifest()


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    lines = ["# TYPE ml_requests_total counter"]
    for (endpoint, status), count in sorted(_requests_total.items()):
        lines.append(f'ml_requests_total{{endpoint="{endpoint}",status="{status}"}} {count}')
    return "\n".join(lines) + "\n"


@app.post("/embed", response_model=EmbedResponse)
async def embed(body: EmbedRequest, request: Request) -> Any:
    if "embed" in _failing():
        return _error(503, "internal_error", "embedder unavailable (FAKE_ML_FAIL)", request)
    if any(len(text) > MAX_TEXT_CHARS for text in body.texts):
        return _error(
            422, "validation_error", f"each text must be at most {MAX_TEXT_CHARS} chars", request
        )
    await asyncio.sleep(_latency_s())
    dim = _dim()
    tokenized = [tokenize(text) for text in body.texts]
    truncated = [len(tokens) > MAX_SEQ_TOKENS for tokens in tokenized]
    tokenized = [tokens[:MAX_SEQ_TOKENS] for tokens in tokenized]
    return EmbedResponse(
        dense=[dense_vector(tokens, dim) for tokens in tokenized] if body.return_dense else None,
        sparse=[sparse_vector(tokens) for tokens in tokenized] if body.return_sparse else None,
        dim=dim,
        truncated=truncated,
        model_version=MODEL_VERSION,
    )


@app.post("/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest, request: Request) -> Any:
    if "rerank" in _failing():
        return _error(503, "internal_error", "reranker unavailable (FAKE_ML_FAIL)", request)
    await asyncio.sleep(_latency_s())
    scored = [
        RerankScore(id=c.id, score=overlap_score(body.query, c.text)) for c in body.candidates
    ]
    scored.sort(key=lambda item: item.score, reverse=True)  # stable: ties keep input order
    if body.top_n is not None:
        scored = scored[: body.top_n]
    return RerankResponse(results=scored, model_version=MODEL_VERSION)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _answer_pieces(lang: str) -> list[str]:
    # Split after spaces so concatenating the pieces gives back the exact text.
    return re.findall(r"\S+\s*", CANNED_ANSWER[lang])


@app.post("/generate", response_model=None)
async def generate(body: GenerateRequest, request: Request) -> Any:
    failing = "generate" in _failing()
    if not body.stream:
        if failing:
            return _error(503, "llm_unavailable", "LLM unavailable (FAKE_ML_FAIL)", request)
        text = CANNED_ANSWER[body.lang]
        return GenerateDone(
            text=text,
            finish_reason="stop",
            usage=GenerateUsage(prompt_tokens=0, completion_tokens=len(_answer_pieces(body.lang))),
            ttft_ms=0,
            total_ms=0,
            model_version=MODEL_VERSION,
        ).model_dump()

    async def stream() -> AsyncIterator[str]:
        started = time.perf_counter()
        if failing:
            yield _sse("error", {"code": "llm_unavailable", "message": "LLM unavailable"})
            return
        await asyncio.sleep(_latency_s())
        ttft_ms: int | None = None
        pieces = _answer_pieces(body.lang)
        for piece in pieces:
            if ttft_ms is None:
                ttft_ms = int((time.perf_counter() - started) * 1000)
            yield _sse("token", {"text": piece})
            await asyncio.sleep(_token_delay_s())
        done = GenerateDone(
            text="".join(pieces),
            finish_reason="stop",
            usage=GenerateUsage(prompt_tokens=0, completion_tokens=len(pieces)),
            ttft_ms=ttft_ms,
            total_ms=int((time.perf_counter() - started) * 1000),
            model_version=MODEL_VERSION,
        )
        yield _sse("done", done.model_dump())

    return StreamingResponse(stream(), media_type="text/event-stream")
