from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.api.context import request_context
from app.api.deps import AnswerServiceDep, BackgroundDep, QueryLogDep, SettingsDep
from app.api.responses import errors
from app.schemas.answer import AnswerRequest
from app.services.search import SearchError

router = APIRouter(tags=["answer"])

SSE_DESCRIPTION = """\
Server-Sent Events stream. Event order: `sources` (once) → `token` (many) → `done` (once),
or `error` instead of `done` if generation fails after the stream started.
The JSON in each event's `data:` line follows the schema named in `x-sse-events`
(`SourcesEvent`, `TokenEvent`, `DoneEvent`, `ErrorEvent`). A `: ping` comment is sent every 15 s.
`done.text` is authoritative: replace the streamed text with it.
Errors before the stream starts (validation, search unavailable) are normal JSON responses.
"""


class EventStreamResponse(StreamingResponse):
    """Only documents the media type in OpenAPI; the handler returns an EventSourceResponse."""

    media_type = "text/event-stream"


def _ping() -> ServerSentEvent:
    return ServerSentEvent(comment="ping")


@router.post(
    "/answer",
    response_class=EventStreamResponse,
    summary="Streamed RAG answer with citations (SSE)",
    responses={
        200: {
            "description": SSE_DESCRIPTION,
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        **errors(422, 429, 503),
    },
)
async def answer(
    body: AnswerRequest,
    request: Request,
    service: AnswerServiceDep,
    query_log: QueryLogDep,
    background: BackgroundDep,
    settings: SettingsDep,
) -> EventSourceResponse:
    ctx = request_context(request, settings.session_salt, "answer")
    try:
        prepared = await service.prepare(body, ctx)
    except SearchError as exc:
        background.spawn(query_log.write(exc.log_values))
        raise
    return EventSourceResponse(
        service.stream(body, prepared),
        ping=settings.sse_ping_s,
        ping_message_factory=_ping,
        # Tell proxies (nginx, Caddy) not to buffer the stream.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
