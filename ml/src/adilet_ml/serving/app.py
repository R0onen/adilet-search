"""FastAPI app implementing `contracts/ml_service.md`."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from prometheus_client import Counter, Histogram, generate_latest

from adilet_ml.schemas import (
    EmbedRequest,
    EmbedResponse,
    GenerateRequest,
    MlHealth,
    RerankRequest,
    RerankResponse,
)
from adilet_ml.serving.engine import EngineLoadError, MlEngine, load_manifest

REQUESTS = Counter("ml_requests_total", "ML requests", ["endpoint", "status"])
LATENCY = Histogram("ml_request_duration_seconds", "ML request latency", ["endpoint"])
BATCH_SIZE = Histogram("ml_batch_size", "ML batch size", ["endpoint"])
TTFT = Histogram("ml_generate_ttft_seconds", "ML generation time to first token")

app = FastAPI(title="Adilet ML service", version="0.1.0")
_engine: MlEngine | None = None
_load_error: str | None = None


@app.on_event("startup")
async def startup() -> None:
    global _engine, _load_error
    try:
        _engine = MlEngine(load_manifest())
        _load_error = None
    except EngineLoadError as exc:
        _engine = None
        _load_error = str(exc)


def engine() -> MlEngine:
    if _engine is None:
        raise EngineLoadError(_load_error or "ML engine is not loaded")
    return _engine


def _error(
    status: int, code: str, message: str, request: Request, details: Any = None
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", request.headers.get("x-request-id"))
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        },
    )


@app.middleware("http")
async def request_id_and_metrics(request: Request, call_next: Any) -> Any:
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    REQUESTS.labels(request.url.path, str(response.status_code)).inc()
    LATENCY.labels(request.url.path).observe(time.perf_counter() - started)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error(422, "validation_error", "Invalid request", request, exc.errors())


@app.exception_handler(EngineLoadError)
async def engine_error(request: Request, exc: EngineLoadError) -> JSONResponse:
    return _error(503, "internal_error", str(exc), request)


@app.get("/health", response_model=MlHealth)
async def health() -> JSONResponse:
    if _engine is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "down",
                "components": {
                    "embedder": "down",
                    "sparse": "down",
                    "reranker": "down",
                    "generator": "unavailable",
                },
                "pipeline_version": None,
            },
        )
    components = {
        "embedder": "ok",
        "sparse": "ok",
        "reranker": "ok",
        "generator": "ok" if _engine.llm_base_url or _engine.manifest.generator else "unavailable",
    }
    return JSONResponse(
        content={
            "status": "ok",
            "components": components,
            "pipeline_version": _engine.pipeline_version,
        }
    )


@app.get("/version")
async def version() -> dict[str, Any]:
    return engine().manifest.model_dump(mode="json")


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> bytes:
    return generate_latest()


@app.post("/embed", response_model=EmbedResponse)
async def embed(body: EmbedRequest, request: Request) -> Any:
    BATCH_SIZE.labels("/embed").observe(len(body.texts))
    try:
        dense, sparse, truncated = engine().embed(
            body.texts,
            body.kind,
            return_dense=body.return_dense,
            return_sparse=body.return_sparse,
        )
    except ValueError as exc:
        return _error(422, "validation_error", str(exc), request)
    return EmbedResponse(
        dense=dense,
        sparse=sparse,
        dim=engine().manifest.embedder.dim,
        truncated=truncated,
        model_version=engine().pipeline_version,
    )


@app.post("/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest) -> RerankResponse:
    BATCH_SIZE.labels("/rerank").observe(len(body.candidates))
    results = engine().rerank(
        body.query,
        [(candidate.id, candidate.text) for candidate in body.candidates],
        body.top_n,
    )
    return RerankResponse(results=results, model_version=engine().pipeline_version)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/generate", response_model=None)
async def generate(body: GenerateRequest) -> Any:
    BATCH_SIZE.labels("/generate").observe(len(body.sources))
    if not body.stream:
        return (await engine().generate_once(body)).model_dump()

    async def stream() -> AsyncIterator[str]:
        async for event, payload in engine().generate_stream(body):
            if event == "done" and payload.get("ttft_ms") is not None:
                TTFT.observe(float(payload["ttft_ms"]) / 1000)
            yield _sse(event, payload)

    return StreamingResponse(stream(), media_type="text/event-stream")
