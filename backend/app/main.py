"""App factory: `uvicorn app.main:create_app --factory`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic.json_schema import models_json_schema

from app.api.v1 import API_PREFIX
from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.schemas.answer import SSE_EVENTS
from app.state import Resources

log = structlog.get_logger(__name__)

DESCRIPTION = """\
Semantic search and source-cited answers over the legislation of Kazakhstan (RU/KK).
The normative description of shapes and semantics is `contracts/api.md`.
Every error uses the shape `{"error": {"code", "message", "details", "request_id"}}`.
"""


def _add_sse_event_schemas(schema: dict[str, Any]) -> None:
    """Publish the SSE payload models as components and link them from `/answer`."""
    _, defs = models_json_schema(
        [(model, "serialization") for model in SSE_EVENTS.values()],
        ref_template="#/components/schemas/{model}",
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in defs.get("$defs", {}).items():
        components.setdefault(name, definition)
    answer_op = schema["paths"][f"{API_PREFIX}/answer"]["post"]
    answer_op["responses"]["200"]["x-sse-events"] = {
        event: {"$ref": f"#/components/schemas/{model.__name__}"}
        for event, model in SSE_EVENTS.items()
    }


def _errors_as_json(schema: dict[str, Any]) -> None:
    """Error bodies are always JSON, even on routes whose success response is SSE or CSV."""
    for operations in schema["paths"].values():
        for operation in operations.values():
            for status, response in operation["responses"].items():
                content = response.get("content", {})
                if status[0] in "45" and "application/json" not in content and content:
                    response["content"] = {"application/json": next(iter(content.values()))}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.resources = Resources.create(settings)
        log.info(
            "startup",
            app_version=settings.app_version,
            git_sha=settings.git_sha,
            environment=settings.environment,
        )
        try:
            yield
        finally:
            await app.state.resources.aclose()
            log.info("shutdown")

    app = FastAPI(
        title="Adilet Search API",
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-Request-Id",
            "X-Session-Id",
        ],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
        max_age=600,
    )
    # Added last = outermost: every response, including CORS preflights and 500s, gets an id.
    app.add_middleware(RequestContextMiddleware)
    app.include_router(v1_router)

    default_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = default_openapi()
            _add_sse_event_schemas(schema)
            _errors_as_json(schema)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app
