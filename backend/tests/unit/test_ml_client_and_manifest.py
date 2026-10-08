import json
from pathlib import Path

import httpx
import pytest

from app.schemas.ml import RerankCandidate
from app.services.manifest import ManifestProvider
from app.services.ml_client import MlClient, MlUnavailable
from dev.fake_ml.app import fake_manifest


def client_for(handler: httpx.MockTransport) -> MlClient:
    return MlClient("http://ml-service:8001", timeout_s=1, connect_timeout_s=1, transport=handler)


async def test_health_parses_503_body() -> None:
    body = {"status": "down", "components": {"embedder": "down"}, "pipeline_version": "0.1.0"}
    ml = client_for(httpx.MockTransport(lambda _: httpx.Response(503, json=body)))
    health = await ml.health()
    assert health.status == "down"
    assert health.components["embedder"] == "down"


@pytest.mark.parametrize(
    ("handler", "kind"),
    [
        (lambda _: httpx.Response(500, json={}), "status"),
        (lambda _: httpx.Response(200, content=b"<html>"), "invalid_json"),
        (lambda _: httpx.Response(200, json={"status": "maybe"}), "invalid_response"),
    ],
)
async def test_health_errors(handler: object, kind: str) -> None:
    ml = client_for(httpx.MockTransport(handler))  # type: ignore[arg-type]
    with pytest.raises(MlUnavailable) as info:
        await ml.health()
    assert info.value.kind == kind


async def test_connection_errors_become_ml_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(MlUnavailable) as info:
        await client_for(httpx.MockTransport(refuse)).version()
    assert info.value.kind == "connection"
    with pytest.raises(MlUnavailable) as info:
        await client_for(httpx.MockTransport(slow)).version()
    assert info.value.kind == "timeout"


async def test_request_id_is_forwarded() -> None:
    from app.core.context import request_id_var

    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-Request-Id"))
        return httpx.Response(200, json=fake_manifest())

    token = request_id_var.set("req-1234567890")
    try:
        await client_for(httpx.MockTransport(handler)).version()
    finally:
        request_id_var.reset(token)
    assert seen == ["req-1234567890"]


async def test_manifest_from_file(tmp_path: Path) -> None:
    path = tmp_path / "model_manifest.json"
    path.write_text(json.dumps(fake_manifest()), encoding="utf-8")
    unused = client_for(httpx.MockTransport(lambda _: httpx.Response(500)))
    provider = ManifestProvider("file", path, unused, retry_s=30)
    manifest = await provider.get()
    assert manifest is not None
    assert manifest.index_compat_id == "fake"
    assert manifest.retrieval.rrf_k == 60


async def test_manifest_failure_is_retried_after_backoff(tmp_path: Path) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={})
        return httpx.Response(200, json=fake_manifest())

    provider = ManifestProvider(
        "service", tmp_path / "unused.json", client_for(httpx.MockTransport(handler)), retry_s=3600
    )
    assert await provider.get() is None
    assert await provider.get() is None  # inside the backoff window: no new call
    assert calls == 1
    provider.invalidate()
    manifest = await provider.get()
    assert manifest is not None
    assert manifest.pipeline_version == "0.0.0-fake"
    assert await provider.get() is manifest  # cached
    assert calls == 2


async def test_missing_manifest_file_returns_none(tmp_path: Path) -> None:
    unused = client_for(httpx.MockTransport(lambda _: httpx.Response(500)))
    provider = ManifestProvider("file", tmp_path / "missing.json", unused, retry_s=0)
    assert await provider.get() is None


def _embed_body(n: int, dense: bool = True, sparse: bool = True) -> dict[str, object]:
    return {
        "dense": [[1.0, 0.0]] * n if dense else None,
        "sparse": [{"indices": [1], "values": [1.0]}] * n if sparse else None,
        "dim": 2,
        "truncated": [False] * n,
        "model_version": "0.1.0",
    }


async def test_embed_sends_flags_and_parses() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=_embed_body(2, sparse=False))

    response = await client_for(httpx.MockTransport(handler)).embed(
        ["a", "b"], "passage", sparse=False
    )
    assert sent == [
        {"texts": ["a", "b"], "kind": "passage", "return_dense": True, "return_sparse": False}
    ]
    assert response.dense == [[1.0, 0.0], [1.0, 0.0]]
    assert response.sparse is None


@pytest.mark.parametrize(
    "body",
    [_embed_body(1), _embed_body(2, sparse=False), {"dense": "nope"}],
    ids=["count-mismatch", "missing-sparse", "malformed"],
)
async def test_embed_rejects_bad_responses(body: dict[str, object]) -> None:
    ml = client_for(httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    with pytest.raises(MlUnavailable) as info:
        await ml.embed(["a", "b"], "query")
    assert info.value.endpoint == "/embed"
    assert info.value.kind == "invalid_response"


async def test_embed_and_rerank_errors() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(MlUnavailable) as info:
        await client_for(httpx.MockTransport(refuse)).embed(["a"], "query")
    assert info.value.kind == "connection"
    with pytest.raises(MlUnavailable) as info:
        await client_for(httpx.MockTransport(slow)).rerank("q", [RerankCandidate(id="x", text="t")])
    assert (info.value.endpoint, info.value.kind) == ("/rerank", "timeout")
    unavailable = httpx.MockTransport(lambda _: httpx.Response(503, json={}))
    with pytest.raises(MlUnavailable) as info:
        await client_for(unavailable).rerank("q", [RerankCandidate(id="x", text="t")])
    assert info.value.kind == "status"


async def test_rerank_parses() -> None:
    body = {"results": [{"id": "x", "score": 2.5}], "model_version": "0.1.0"}
    ml = client_for(httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    response = await ml.rerank("q", [RerankCandidate(id="x", text="t")])
    assert response.results[0].score == 2.5


GENERATE = {
    "question": "q",
    "lang": "ru",
    "sources": [{"ref": 1, "article_id": "K1:ru:a1", "title": "t", "text": "x"}],
}


async def test_generate_stream_parses_sse() -> None:
    raw = (
        ": ping\n\n"
        'event: token\ndata: {"text": "Привет "}\n\n'
        'event: token\ndata: {"text":\ndata: "мир"}\n\n'  # multi-line data
        'event: done\ndata: {"text": "Привет мир", "finish_reason": "stop"}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200, content=raw.encode(), headers={"content-type": "text/event-stream"}
        )

    from app.schemas.ml import GenerateRequest

    ml = client_for(httpx.MockTransport(handler))
    events = [
        e async for e in ml.generate_stream(GenerateRequest.model_validate(GENERATE), timeout_s=5)
    ]
    assert [e.event for e in events] == ["token", "token", "done"]
    assert events[1].data == {"text": "мир"}
    assert events[2].data["text"] == "Привет мир"


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (httpx.Response(503, json={}), "status"),
        (httpx.Response(200, content=b"event: token\ndata: {not json\n\n"), "invalid_json"),
    ],
)
async def test_generate_stream_errors(response: httpx.Response, kind: str) -> None:
    from app.schemas.ml import GenerateRequest

    ml = client_for(httpx.MockTransport(lambda _: response))
    with pytest.raises(MlUnavailable) as info:
        async for _ in ml.generate_stream(GenerateRequest.model_validate(GENERATE), timeout_s=5):
            pass
    assert info.value.kind == kind
