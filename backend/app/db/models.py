"""Postgres schema (contracts/data_schema.md §3, §4, §8). Changes go through Alembic migrations.

Enumerations are TEXT + CHECK constraints rather than Postgres enum types, so adding a value is a
one-line migration.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


LANGS = ("ru", "kk")
DOC_TYPES = ("code", "law", "decree", "resolution", "order", "other")
DOC_STATUSES = ("in_force", "repealed", "not_yet_in_force")
UNIT_TYPES = ("article", "paragraph", "chapter", "preamble", "annex")
UNIT_STATUSES = ("in_force", "excluded")
MODES = ("hybrid", "semantic", "keyword")
CLIENTS = ("web", "api-key", "unknown")
ANSWER_STATUSES = ("completed", "error", "cancelled")
FEEDBACK_TARGETS = ("result", "answer")
JOB_KINDS = ("reindex",)
JOB_STATUSES = ("queued", "running", "succeeded", "failed")

# Full-text config per language: Russian stemming for ru, no stemming for kk.
TSV_EXPRESSION = (
    "setweight(to_tsvector(CASE WHEN lang = 'ru' THEN 'russian'::regconfig "
    "ELSE 'simple'::regconfig END, coalesce(unit_title, '')), 'A') || "
    "setweight(to_tsvector(CASE WHEN lang = 'ru' THEN 'russian'::regconfig "
    "ELSE 'simple'::regconfig END, text), 'B')"
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# --- corpus -------------------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(_in("lang", LANGS), name="lang"),
        CheckConstraint(_in("doc_type", DOC_TYPES), name="doc_type"),
        CheckConstraint(_in("status", DOC_STATUSES), name="status"),
        Index("ix_documents_lang_doc_type", "lang", "doc_type"),
    )

    doc_id: Mapped[str] = mapped_column(Text, primary_key=True)
    lang: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    short_title: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[str | None] = mapped_column(Text)
    adopted_date: Mapped[date | None] = mapped_column(Date)
    revision_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    corpus_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["doc_id", "lang"], ["documents.doc_id", "documents.lang"], ondelete="CASCADE"
        ),
        UniqueConstraint("doc_id", "lang", "unit_key"),
        CheckConstraint(_in("lang", LANGS), name="lang"),
        CheckConstraint(_in("unit_type", UNIT_TYPES), name="unit_type"),
        CheckConstraint(_in("unit_status", UNIT_STATUSES), name="unit_status"),
        Index("ix_articles_doc_id_lang_unit_order", "doc_id", "lang", "unit_order"),
        Index("ix_articles_tsv", "tsv", postgresql_using="gin"),
    )

    article_id: Mapped[str] = mapped_column(Text, primary_key=True)
    doc_id: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str] = mapped_column(Text, nullable=False)
    unit_type: Mapped[str] = mapped_column(Text, nullable=False)
    unit_key: Mapped[str] = mapped_column(Text, nullable=False)
    unit_number: Mapped[str | None] = mapped_column(Text)
    unit_title: Mapped[str | None] = mapped_column(Text)
    unit_order: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_status: Mapped[str] = mapped_column(Text, nullable=False)
    section_title: Mapped[str | None] = mapped_column(Text)
    chapter_title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    amendment_notes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=sql_text("'{}'::text[]")
    )
    has_amendments: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    parallel_article_id: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    corpus_version: Mapped[str] = mapped_column(Text, nullable=False)
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed(TSV_EXPRESSION, persisted=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


# --- logs ---------------------------------------------------------------------------------


class QueryLog(Base):
    """One row per /search or /answer call. Results are kept as JSONB (rank, ids, scores)."""

    __tablename__ = "query_logs"
    __table_args__ = (
        CheckConstraint(_in("lang", LANGS), name="lang"),
        CheckConstraint(_in("mode", MODES), name="mode"),
        CheckConstraint(_in("client", CLIENTS), name="client"),
        Index("ix_query_logs_created_at", "created_at"),
        Index("ix_query_logs_lang_created_at", "lang", "created_at"),
        Index("ix_query_logs_mode_created_at", "mode", "created_at"),
        Index(
            "ix_query_logs_zero_results_created_at",
            "created_at",
            postgresql_where=sql_text("zero_results"),
        ),
        Index(
            "ix_query_logs_degraded_created_at",
            "created_at",
            postgresql_where=sql_text("is_degraded"),
        ),
        Index("ix_query_logs_query_norm", "query_norm"),
        Index("ix_query_logs_session_hash", "session_hash"),
    )

    query_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = _created_at()
    session_hash: Mapped[str | None] = mapped_column(Text)
    client: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    ua_family: Mapped[str | None] = mapped_column(Text)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, server_default="search")
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_norm: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    top_k: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    result_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    zero_results: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    top_article_id: Mapped[str | None] = mapped_column(Text)
    total_candidates: Mapped[int | None] = mapped_column(Integer)
    results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )
    timing_ms: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    search_ms: Mapped[int | None] = mapped_column(Integer)
    degraded: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=sql_text("'{}'::text[]")
    )
    is_degraded: Mapped[bool] = mapped_column(
        Boolean, Computed("cardinality(degraded) > 0", persisted=True)
    )
    has_answer: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    error_code: Mapped[str | None] = mapped_column(Text)
    pipeline_version: Mapped[str | None] = mapped_column(Text)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint(_in("status", ANSWER_STATUSES), name="status"),
        Index("ix_answers_created_at", "created_at"),
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_logs.query_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = _created_at()
    status: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )
    citations: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, server_default=sql_text("'{}'::smallint[]")
    )
    invalid_citations_removed: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="0"
    )
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    finish_reason: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    search_ms: Mapped[int | None] = mapped_column(Integer)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    total_ms: Mapped[int | None] = mapped_column(Integer)
    pipeline_version: Mapped[str | None] = mapped_column(Text)


class Feedback(Base):
    """A repeat for the same (session, query, target, article) overwrites the earlier row."""

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(_in("target", FEEDBACK_TARGETS), name="target"),
        CheckConstraint("rating IN (1, -1)", name="rating"),
        CheckConstraint("target <> 'result' OR article_id IS NOT NULL", name="result_has_article"),
        UniqueConstraint(
            "session_hash",
            "query_id",
            "target",
            "article_id",
            name="uq_feedback_session_query_target_article",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_feedback_created_at", "created_at"),
        Index("ix_feedback_query_id", "query_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("query_logs.query_id", ondelete="CASCADE"), nullable=False
    )
    session_hash: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    article_id: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


# --- index management ---------------------------------------------------------------------


class IndexJob(Base):
    __tablename__ = "index_jobs"
    __table_args__ = (
        CheckConstraint(_in("kind", JOB_KINDS), name="kind"),
        CheckConstraint(_in("status", JOB_STATUSES), name="status"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="progress"),
        Index("ix_index_jobs_created_at", "created_at"),
        # At most one active job at a time, enforced by the database.
        Index(
            "uq_index_jobs_one_active",
            sql_text("(true)"),
            unique=True,
            postgresql_where=sql_text("status IN ('queued', 'running')"),
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="reindex")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    progress: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    message: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    collection: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IndexState(Base):
    """One row per Qdrant collection the backend has built."""

    __tablename__ = "index_state"

    collection: Mapped[str] = mapped_column(Text, primary_key=True)
    pipeline_version: Mapped[str] = mapped_column(Text, nullable=False)
    index_compat_id: Mapped[str] = mapped_column(Text, nullable=False)
    corpus_version: Mapped[str | None] = mapped_column(Text)
    points_count: Mapped[int] = mapped_column(Integer, nullable=False)
    documents_count: Mapped[int | None] = mapped_column(Integer)
    articles_count: Mapped[int | None] = mapped_column(Integer)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("index_jobs.job_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created_at()


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = _created_at()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
