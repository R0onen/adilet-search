"""Integration tests need real services. Start them with:

    docker compose --profile dev up -d postgres qdrant fake-ml

and point the tests at them (defaults shown):

    TEST_DATABASE_URL=postgresql+asyncpg://adilet:adilet@localhost:5432/adilet_test
    TEST_QDRANT_URL=http://localhost:6333
    TEST_ML_SERVICE_URL=http://localhost:8001

The test database is created if missing and is dropped/recreated by the migration tests:
never point TEST_DATABASE_URL at a database with data you want to keep.
"""

import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from alembic.config import Config

from tests.conftest import REPO_ROOT

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://adilet:adilet@localhost:5432/adilet_test"
)
TEST_QDRANT_URL = os.getenv("TEST_QDRANT_URL", "http://localhost:6333")
TEST_ML_SERVICE_URL = os.getenv("TEST_ML_SERVICE_URL", "http://localhost:8001")


def plain_dsn(url: str, database: str | None = None) -> str:
    """asyncpg DSN from a SQLAlchemy URL, optionally for another database."""
    parts = urlsplit(url.replace("postgresql+asyncpg://", "postgresql://"))
    path = f"/{database}" if database else parts.path
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


async def _ensure_database(url: str) -> None:
    name = urlsplit(url).path.lstrip("/")
    conn = await asyncpg.connect(plain_dsn(url, "postgres"))
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def database_url() -> str:
    asyncio.run(_ensure_database(TEST_DATABASE_URL))
    return TEST_DATABASE_URL


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
