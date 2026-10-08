from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.responses import errors
from app.core.errors import NotImplementedYet
from app.schemas.answer import AnswerRequest

router = APIRouter(tags=["answer"])

SSE_DESCRIPTION = """\
Server-Sent Events stream. Event order: `sources` (once) → `token` (many) → `done` (once),
or `error` instead of `done` if generation fails after the stream started.
The JSON in each event's `data:` line follows the schema named in `x-sse-events`
(`SourcesEvent`, `TokenEvent`, `DoneEvent`, `ErrorEvent`). A `: ping` comment is sent every 15 s.
`done.text` is authoritative: replace the streamed text with it.
"""


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


@router.post(
    "/answer",
    response_class=EventStreamResponse,
    summary="Streamed RAG answer with citations (SSE)",
    responses={
        200: {
            "description": SSE_DESCRIPTION,
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        **errors(422, 429, 501, 503),
    },
)
async def answer(body: AnswerRequest) -> EventStreamResponse:
    raise NotImplementedYet("POST /answer")
