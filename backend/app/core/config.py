"""Application settings, read from environment variables (see `.env.example`)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app import __version__

# Values that are only acceptable outside production.
DEV_SESSION_SALT = "dev-only-session-salt"
DEV_JWT_SECRET = "dev-only-jwt-secret-change-me-in-production"  # noqa: S105 - rejected in prod


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- app ---
    environment: Literal["dev", "test", "prod"] = "dev"
    app_version: str = __version__
    git_sha: str = "unknown"
    log_level: str = "INFO"
    log_json: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- storage ---
    database_url: str = "postgresql+asyncpg://adilet:adilet@localhost:5432/adilet"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_alias: str = "legal_chunks"
    qdrant_timeout_s: float = 5.0
    # gRPC is ~30x faster than REST per query here (1.5 ms vs 44 ms, measured in BE-02).
    qdrant_prefer_grpc: bool = True
    qdrant_grpc_port: int = 6334

    # --- ML service ---
    ml_service_url: str = "http://localhost:8001"
    ml_connect_timeout_s: float = 2.0
    ml_timeout_s: float = 10.0
    manifest_source: Literal["file", "service"] = "service"
    model_manifest_path: str = "../ml/models/model_manifest.json"
    manifest_retry_s: float = 30.0

    # --- search (per-stage time budgets; /search p95 target is 2 s) ---
    search_embed_timeout_s: float = Field(default=2.0, gt=0)
    search_retrieve_timeout_s: float = Field(default=2.0, gt=0)
    search_rerank_timeout_s: float = Field(default=1.5, gt=0)
    index_state_ttl_s: float = Field(default=30.0, ge=0)
    # Overrides the manifest's retrieval.rerank_top_n; 0 = no rerank (fused order). A latency lever,
    # and a way to bypass a reranker that hurts quality (e.g. ML's bootstrap word-overlap reranker).
    search_rerank_top_n: int | None = Field(default=None, ge=0, le=100)

    # --- answer (SSE) ---
    answer_timeout_s: float = Field(default=90.0, gt=0)
    # ml_service.md /generate: max_tokens at most 1024.
    answer_max_tokens: int = Field(default=512, ge=1, le=1024)
    answer_temperature: float = Field(default=0.1, ge=0, le=2)
    sse_ping_s: float = Field(default=15.0, gt=0)

    # --- health ---
    health_timeout_s: float = Field(default=2.0, gt=0)

    # --- privacy ---
    session_salt: str = DEV_SESSION_SALT

    # --- admin auth ---
    # The admin user is created or updated at startup when both values are set.
    admin_username: str | None = None
    admin_password_hash: str | None = None  # bcrypt; `python -m app.cli hash-password`
    jwt_secret: str = DEV_JWT_SECRET
    jwt_ttl_s: int = Field(default=8 * 3600, gt=0)

    # --- rate limits (requests per minute per session + IP; 0 = unlimited) ---
    rate_limit_search: int = Field(default=60, ge=0)
    rate_limit_answer: int = Field(default=10, ge=0)
    rate_limit_login: int = Field(default=5, ge=0)
    # Server-to-server callers send X-API-Key; a valid key multiplies the limits.
    api_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_key_limit_factor: int = Field(default=10, ge=1)
    max_body_bytes: int = Field(default=64 * 1024, gt=0)

    # --- resilience ---
    # After `breaker_failures` consecutive failures a dependency is skipped for `breaker_reset_s`.
    breaker_failures: int = Field(default=5, ge=1)
    breaker_reset_s: float = Field(default=20.0, gt=0)
    # Per-process cache of query embeddings and search responses (0 = off).
    cache_ttl_s: float = Field(default=300.0, ge=0)
    cache_size: int = Field(default=2000, ge=1)

    # --- admin reindex ---
    # `processed` / `sample` live under this directory (mounted read-only in Docker).
    data_dir: str = "../data"

    @field_validator("cors_origins", "api_keys", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "qdrant_api_key",
        "search_rerank_top_n",
        "admin_username",
        "admin_password_hash",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _no_dev_secrets_in_prod(self) -> "Settings":
        if self.environment == "prod" and self.session_salt == DEV_SESSION_SALT:
            raise ValueError("SESSION_SALT must be set to a strong secret in production")
        if self.environment == "prod" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set to a strong secret in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
