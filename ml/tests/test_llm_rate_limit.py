import asyncio

import httpx
import pytest

from adilet_ml.serving import engine
from adilet_ml.serving.engine import _open_llm_stream, _retry_after_s


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("2", 2.0),
        ("0.5", 0.5),
        ("30", 30.0),
        ("31", None),
        ("-1", None),
        ("soon", None),
        (None, None),
    ],
)
def test_retry_after_is_bounded(header: str | None, expected: float | None) -> None:
    assert _retry_after_s(header) == expected


def _open(statuses: list[tuple[int, dict[str, str]]]) -> tuple[int, int]:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        status, headers = statuses[min(calls, len(statuses) - 1)]
        calls += 1
        return httpx.Response(status, headers=headers, text="data: [DONE]\n\n")

    async def run() -> int:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response = await _open_llm_stream(client, "http://llm/v1/chat/completions", {})
            await response.aclose()
            return response.status_code

    return asyncio.run(run()), calls


def test_rate_limited_request_is_retried_once(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []

    async def no_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(engine.asyncio, "sleep", no_sleep)
    assert _open([(429, {"retry-after": "3"}), (200, {})]) == (200, 2)
    assert waits == [3.0]


def test_no_retry_without_a_short_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(seconds: float) -> None:
        raise AssertionError("must not wait")

    monkeypatch.setattr(engine.asyncio, "sleep", fail)
    assert _open([(429, {"retry-after": "600"}), (200, {})]) == (429, 1)
    assert _open([(429, {}), (200, {})]) == (429, 1)
    assert _open([(200, {})]) == (200, 1)
