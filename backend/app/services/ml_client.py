"""HTTP client for the internal ML service (contracts/ml_service.md).

One pooled `httpx.AsyncClient` per process. Every call has a timeout. Failures are raised as
`MlUnavailable` so callers can degrade instead of failing.
"""

from typing import Any, Literal

import httpx
import structlog
from pydantic import ValidationError

from app.core.context import current_request_id
from app.schemas.ml import (
    EmbedRequest,
    EmbedResponse,
    Manifest,
    MlHealth,
    RerankCandidate,
    RerankRequest,
    RerankResponse,
)

log = structlog.get_logger(__name__)


class MlUnavailable(Exception):
    """The ML service is unreachable, timed out, or answered with an error."""

    def __init__(self, endpoint: str, kind: str, detail: str = "") -> None:
        super().__init__(f"ml-service {endpoint}: {kind} {detail}".strip())
        self.endpoint = endpoint
        self.kind = kind


async def _add_request_id(request: httpx.Request) -> None:
    request_id = current_request_id()
    if request_id:
        request.headers["X-Request-Id"] = request_id


class MlClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        connect_timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_s, connect=connect_timeout_s),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            event_hooks={"request": [_add_request_id]},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(self, endpoint: str, timeout_s: float | None = None) -> Any:
        try:
            response = await self._client.get(
                endpoint, timeout=timeout_s if timeout_s is not None else httpx.USE_CLIENT_DEFAULT
            )
        except httpx.TimeoutException as exc:
            raise MlUnavailable(endpoint, "timeout") from exc
        except httpx.HTTPError as exc:
            raise MlUnavailable(endpoint, "connection", type(exc).__name__) from exc
        # /health answers 503 with a valid body when the service is down.
        if response.status_code >= 400 and not (
            endpoint == "/health" and response.status_code == 503
        ):
            raise MlUnavailable(endpoint, "status", str(response.status_code))
        try:
            return response.json()
        except ValueError as exc:
            raise MlUnavailable(endpoint, "invalid_json") from exc

    async def _post_json(self, endpoint: str, body: dict[str, Any], timeout_s: float | None) -> Any:
        try:
            response = await self._client.post(
                endpoint,
                json=body,
                timeout=timeout_s if timeout_s is not None else httpx.USE_CLIENT_DEFAULT,
            )
        except httpx.TimeoutException as exc:
            raise MlUnavailable(endpoint, "timeout") from exc
        except httpx.HTTPError as exc:
            raise MlUnavailable(endpoint, "connection", type(exc).__name__) from exc
        if response.status_code >= 400:
            raise MlUnavailable(endpoint, "status", str(response.status_code))
        try:
            return response.json()
        except ValueError as exc:
            raise MlUnavailable(endpoint, "invalid_json") from exc

    async def embed(
        self,
        texts: list[str],
        kind: Literal["query", "passage"],
        *,
        dense: bool = True,
        sparse: bool = True,
        timeout_s: float | None = None,
    ) -> EmbedResponse:
        request = EmbedRequest(texts=texts, kind=kind, return_dense=dense, return_sparse=sparse)
        data = await self._post_json("/embed", request.model_dump(), timeout_s)
        try:
            response = EmbedResponse.model_validate(data)
        except ValidationError as exc:
            raise MlUnavailable("/embed", "invalid_response") from exc
        expected = len(texts)
        if (dense and (response.dense is None or len(response.dense) != expected)) or (
            sparse and (response.sparse is None or len(response.sparse) != expected)
        ):
            raise MlUnavailable("/embed", "invalid_response", "vector count mismatch")
        return response

    async def rerank(
        self,
        query: str,
        candidates: list[RerankCandidate],
        *,
        timeout_s: float | None = None,
    ) -> RerankResponse:
        request = RerankRequest(query=query, candidates=candidates, top_n=None)
        data = await self._post_json("/rerank", request.model_dump(), timeout_s)
        try:
            return RerankResponse.model_validate(data)
        except ValidationError as exc:
            raise MlUnavailable("/rerank", "invalid_response") from exc

    async def health(self, timeout_s: float | None = None) -> MlHealth:
        data = await self._get_json("/health", timeout_s)
        try:
            return MlHealth.model_validate(data)
        except ValidationError as exc:
            raise MlUnavailable("/health", "invalid_response") from exc

    async def version(self) -> Manifest:
        data = await self._get_json("/version")
        try:
            return Manifest.model_validate(data)
        except ValidationError as exc:
            raise MlUnavailable("/version", "invalid_response") from exc
