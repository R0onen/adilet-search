"""Model manifest loading (contracts/ml_service.md §3).

`MANIFEST_SOURCE=file` reads `MODEL_MANIFEST_PATH`; `service` asks `ml-service /version`.
A successful load is cached for the process lifetime. A failed load is retried at most every
`MANIFEST_RETRY_S`, so the backend starts (and degrades) while ML is not up yet.
"""

import json
import time
from pathlib import Path
from typing import Literal

import structlog
from pydantic import ValidationError

from app.schemas.ml import Manifest
from app.services.ml_client import MlClient, MlUnavailable

log = structlog.get_logger(__name__)


class ManifestProvider:
    def __init__(
        self,
        source: Literal["file", "service"],
        path: Path,
        ml_client: MlClient,
        retry_s: float,
    ) -> None:
        self._source = source
        self._path = path
        self._ml = ml_client
        self._retry_s = retry_s
        self._manifest: Manifest | None = None
        self._last_attempt = float("-inf")

    @property
    def cached(self) -> Manifest | None:
        return self._manifest

    def invalidate(self) -> None:
        self._manifest = None
        self._last_attempt = float("-inf")

    async def get(self) -> Manifest | None:
        if self._manifest is not None:
            return self._manifest
        now = time.monotonic()
        if now - self._last_attempt < self._retry_s:
            return None
        self._last_attempt = now
        try:
            self._manifest = await self._load()
        except (OSError, ValueError, ValidationError, MlUnavailable) as exc:
            log.warning("manifest_unavailable", source=self._source, error=str(exc))
            return None
        log.info(
            "manifest_loaded",
            source=self._source,
            pipeline_version=self._manifest.pipeline_version,
            index_compat_id=self._manifest.index_compat_id,
        )
        return self._manifest

    async def _load(self) -> Manifest:
        if self._source == "file":
            return Manifest.model_validate(json.loads(self._path.read_text(encoding="utf-8")))
        return await self._ml.version()
