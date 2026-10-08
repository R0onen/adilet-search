"""SQL access for the corpus, query logs and index bookkeeping. Callers own the session."""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, delete, func, literal_column, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article, Document, IndexJob, IndexState, QueryLog

BATCH_ROWS = 500

DOCUMENT_COLUMNS = (
    "doc_id",
    "lang",
    "title",
    "short_title",
    "doc_type",
    "number",
    "adopted_date",
    "revision_date",
    "status",
    "source_url",
    "article_count",
    "scraped_at",
    "corpus_version",
)
ARTICLE_COLUMNS = (
    "article_id",
    "doc_id",
    "lang",
    "unit_type",
    "unit_key",
    "unit_number",
    "unit_title",
    "unit_order",
    "unit_status",
    "section_title",
    "chapter_title",
    "text",
    "amendment_notes",
    "has_amendments",
    "source_url",
    "parallel_article_id",
    "content_hash",
    "corpus_version",
)


@dataclass
class UpsertCounts:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    def __add__(self, other: "UpsertCounts") -> "UpsertCounts":
        return UpsertCounts(
            self.inserted + other.inserted,
            self.updated + other.updated,
            self.unchanged + other.unchanged,
        )


async def _upsert(
    session: AsyncSession,
    model: type[Document] | type[Article],
    columns: Sequence[str],
    keys: Sequence[str],
    rows: Sequence[dict[str, Any]],
) -> UpsertCounts:
    """INSERT … ON CONFLICT DO UPDATE only when a column changed; unchanged rows are skipped."""
    counts = UpsertCounts()
    table = model.__table__
    changing = [c for c in columns if c not in keys]
    for start in range(0, len(rows), BATCH_ROWS):
        batch = [{c: row[c] for c in columns} for row in rows[start : start + BATCH_ROWS]]
        base = insert(model).values(batch)
        stmt: Any = base.on_conflict_do_update(
            index_elements=list(keys),
            set_={**{c: base.excluded[c] for c in changing}, "updated_at": func.now()},
            where=tuple_(*[table.c[c] for c in changing]).is_distinct_from(
                tuple_(*[base.excluded[c] for c in changing])
            ),
        ).returning(literal_column("(xmax = 0)").label("inserted"))
        result = (await session.execute(stmt)).scalars().all()
        inserted = sum(1 for flag in result if flag)
        counts += UpsertCounts(inserted, len(result) - inserted, len(batch) - len(result))
    return counts


async def upsert_documents(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> UpsertCounts:
    return await _upsert(session, Document, DOCUMENT_COLUMNS, ("doc_id", "lang"), rows)


async def upsert_articles(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> UpsertCounts:
    return await _upsert(session, Article, ARTICLE_COLUMNS, ("article_id",), rows)


async def prune_corpus(
    session: AsyncSession, doc_keys: Iterable[tuple[str, str]], article_ids: Iterable[str]
) -> tuple[int, int]:
    """Delete documents and articles that are not in the indexed dataset."""
    keep_articles = list(article_ids)
    keep_docs = list(doc_keys)
    articles = await session.execute(
        delete(Article).where(Article.article_id.not_in(keep_articles))
        if keep_articles
        else delete(Article)
    )
    documents = await session.execute(
        delete(Document).where(tuple_(Document.doc_id, Document.lang).not_in(keep_docs))
        if keep_docs
        else delete(Document)
    )
    return documents.rowcount or 0, articles.rowcount or 0  # type: ignore[attr-defined]


# --- reads for the API --------------------------------------------------------------------


def _article_with_doc() -> Select[Article, Document]:
    return select(Article, Document).join(
        Document, and_(Document.doc_id == Article.doc_id, Document.lang == Article.lang)
    )


async def fetch_articles(
    session: AsyncSession, article_ids: Sequence[str]
) -> dict[str, tuple[Article, Document]]:
    """Article + document rows for many ids in one query."""
    if not article_ids:
        return {}
    rows = await session.execute(_article_with_doc().where(Article.article_id.in_(article_ids)))
    return {row[0].article_id: (row[0], row[1]) for row in rows}


async def get_article(session: AsyncSession, article_id: str) -> tuple[Article, Document] | None:
    row = (
        await session.execute(_article_with_doc().where(Article.article_id == article_id))
    ).first()
    return (row[0], row[1]) if row else None


async def neighbour_ids(session: AsyncSession, article: Article) -> tuple[str | None, str | None]:
    same_doc = and_(Article.doc_id == article.doc_id, Article.lang == article.lang)
    prev_id = await session.scalar(
        select(Article.article_id)
        .where(same_doc, Article.unit_order < article.unit_order)
        .order_by(Article.unit_order.desc())
        .limit(1)
    )
    next_id = await session.scalar(
        select(Article.article_id)
        .where(same_doc, Article.unit_order > article.unit_order)
        .order_by(Article.unit_order.asc())
        .limit(1)
    )
    return prev_id, next_id


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_documents(
    session: AsyncSession,
    lang: str,
    doc_type: str | None,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Document], int]:
    conditions = [Document.lang == lang]
    if doc_type:
        conditions.append(Document.doc_type == doc_type)
    if q:
        pattern = f"%{_escape_like(q.strip())}%"
        conditions.append(
            Document.title.ilike(pattern, escape="\\")
            | Document.short_title.ilike(pattern, escape="\\")
        )
    total = await session.scalar(select(func.count()).select_from(Document).where(*conditions))
    rows = await session.scalars(
        select(Document)
        .where(*conditions)
        .order_by(Document.doc_type, Document.short_title, Document.doc_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total or 0


async def get_document(session: AsyncSession, doc_id: str, lang: str) -> Document | None:
    return await session.get(Document, (doc_id, lang))


async def document_toc(session: AsyncSession, doc_id: str, lang: str) -> list[Article]:
    rows = await session.scalars(
        select(Article)
        .where(Article.doc_id == doc_id, Article.lang == lang)
        .order_by(Article.unit_order)
    )
    return list(rows)


# --- query logs ---------------------------------------------------------------------------


async def insert_query_log(session: AsyncSession, values: dict[str, Any]) -> None:
    await session.execute(insert(QueryLog).values(**values))


# --- index bookkeeping --------------------------------------------------------------------


async def create_job(session: AsyncSession, params: dict[str, Any]) -> uuid.UUID:
    job_id = uuid.uuid4()
    await session.execute(
        insert(IndexJob).values(job_id=job_id, kind="reindex", status="queued", params=params)
    )
    return job_id


async def update_job(session: AsyncSession, job_id: uuid.UUID, **values: Any) -> None:
    await session.execute(update(IndexJob).where(IndexJob.job_id == job_id).values(**values))


def now_utc() -> datetime:
    return datetime.now(UTC)


async def record_index_state(session: AsyncSession, values: dict[str, Any]) -> None:
    stmt = insert(IndexState).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["collection"],
        set_={k: stmt.excluded[k] for k in values if k != "collection"},
    )
    await session.execute(stmt)


async def get_index_state(session: AsyncSession, collection: str) -> IndexState | None:
    return await session.get(IndexState, collection)
