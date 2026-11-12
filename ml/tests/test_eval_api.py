import importlib.util
import json
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "eval_api", Path(__file__).parents[1] / "scripts/eval_api.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_api_evaluation_reads_contract_results_and_exposes_degradation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["lang"] == "kk"
        return httpx.Response(
            200,
            json={
                "results": [{"article": {"article_id": "K1500000414:kk:a68"}}],
                "degraded": ["rerank"],
            },
        )

    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)) as client:
        ids, elapsed, degraded = module._search(
            client, {"query_id": "q1", "text": "жұмыс уақыты", "lang": "kk"}, "hybrid", 50
        )
    assert ids == ["K1500000414:kk:a68"]
    assert elapsed >= 0
    assert degraded == ["rerank"]


def test_api_evaluation_does_not_convert_http_failure_to_empty_ranking() -> None:
    with (
        httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(503, json={"error": {"code": "upstream_unavailable"}})
            ),
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        module._search(client, {"text": "test", "lang": "ru"}, "hybrid", 50)
