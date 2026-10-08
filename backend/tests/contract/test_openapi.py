"""contracts/openapi.json is fresh, self-consistent and covers every endpoint in api.md."""

import re
from typing import Any

import pytest

from app.export_openapi import DEFAULT_OUTPUT, build_schema, render
from tests.conftest import CONTRACTS

ENDPOINT_HEADING = re.compile(r"^### `(GET|POST|PUT|PATCH|DELETE) (/[^`?\s]*)", re.MULTILINE)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return build_schema()


def _refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        found = [node["$ref"]] if isinstance(node.get("$ref"), str) else []
        return found + [ref for value in node.values() for ref in _refs(value)]
    if isinstance(node, list):
        return [ref for value in node for ref in _refs(value)]
    return []


def test_committed_openapi_is_up_to_date(schema: dict[str, Any]) -> None:
    assert DEFAULT_OUTPUT.exists(), "run `uv run python -m app.export_openapi`"
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render(schema), (
        "contracts/openapi.json is stale: run `uv run python -m app.export_openapi`"
    )


def test_every_ref_resolves(schema: dict[str, Any]) -> None:
    components = schema["components"]["schemas"]
    for ref in _refs(schema):
        assert ref.startswith("#/components/schemas/"), ref
        assert ref.rsplit("/", 1)[1] in components, ref


def test_every_contract_endpoint_is_present(schema: dict[str, Any]) -> None:
    api_md = (CONTRACTS / "api.md").read_text(encoding="utf-8")
    documented = {(m.lower(), "/api/v1" + p) for m, p in ENDPOINT_HEADING.findall(api_md)}
    assert len(documented) == 16
    present = {(method, path) for path, ops in schema["paths"].items() for method in ops}
    assert documented == present


def test_errors_use_contract_shape(schema: dict[str, Any]) -> None:
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            for status, response in op["responses"].items():
                if status.startswith(("4", "5")):
                    ref = response["content"]["application/json"]["schema"]["$ref"]
                    assert ref.endswith(("/ErrorResponse", "/HealthResponse")), (
                        method,
                        path,
                        status,
                    )


def test_sse_events_are_published(schema: dict[str, Any]) -> None:
    ok = schema["paths"]["/api/v1/answer"]["post"]["responses"]["200"]
    assert "text/event-stream" in ok["content"]
    assert set(ok["x-sse-events"]) == {"sources", "token", "done", "error"}
    for name in ("SourcesEvent", "TokenEvent", "DoneEvent", "ErrorEvent"):
        assert name in schema["components"]["schemas"]


def test_admin_routes_declare_bearer_auth(schema: dict[str, Any]) -> None:
    for path, ops in schema["paths"].items():
        if path.startswith("/api/v1/admin/") and path != "/api/v1/admin/login":
            for op in ops.values():
                assert op.get("security"), path
