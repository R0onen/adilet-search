"""Full-text fallback: Postgres search over `articles.tsv` when the semantic path is down.

Used when the ML service or Qdrant is unavailable (timeout, connection error, open circuit) or
the index is incompatible with the models. The response then carries `degraded: ["semantic"]`
and `score_type: "fts"`. It is keyword search only: no embeddings, no reranking.
"""

from sqlalchemy import ColumnElement, Text, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Article, Document
from app.schemas.search import SearchFilters


def _config(lang: str) -> str:
    # The same configurations as the generated `tsv` column (see TSV_EXPRESSION in models.py).
    return "russian" if lang == "ru" else "simple"


class FtsFallback:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessionmaker

    async def search(
        self, query: str, lang: str, filters: SearchFilters, limit: int
    ) -> list[tuple[Article, Document, float]]:
        """Best articles by `ts_rank_cd`. Words are OR-ed: a plain-language question rarely has
        every word in one article, and AND would return nothing."""
        config: ColumnElement[str] = literal_column(f"'{_config(lang)}'::regconfig")
        strict = func.websearch_to_tsquery(config, query)
        # websearch_to_tsquery ANDs the words; rewrite its `&` into `|` to rank partial matches.
        loose = func.to_tsquery(config, func.replace(cast(strict, Text), "&", "|"))
        # 1 | 32: damp long articles (they match many words) and scale the rank into 0..1.
        rank = func.ts_rank_cd(Article.tsv, loose, 33).label("rank")
        stmt = (
            select(Article, Document, rank)
            .join(Document, (Document.doc_id == Article.doc_id) & (Document.lang == Article.lang))
            .where(Article.lang == lang, Article.tsv.op("@@")(loose))
        )
        if filters.doc_ids:
            stmt = stmt.where(Article.doc_id.in_(filters.doc_ids))
        if filters.doc_types:
            stmt = stmt.where(Document.doc_type.in_(filters.doc_types))
        if filters.in_force_only:
            stmt = stmt.where(Document.status == "in_force", Article.unit_status == "in_force")
        if filters.date_from:
            stmt = stmt.where(Document.adopted_date >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(Document.adopted_date <= filters.date_to)
        stmt = stmt.order_by(rank.desc(), Article.article_id).limit(limit)
        async with self._sessions() as session:
            rows = (await session.execute(stmt)).all()
        return [(row[0], row[1], float(row[2])) for row in rows]
