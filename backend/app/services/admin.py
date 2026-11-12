"""Admin read models: usage statistics and the query log (contracts/api.md §4).

Plain SQL on purpose: these are reporting queries (percentiles, generate_series, FILTER), and the
SQL is easier to check with EXPLAIN than an ORM expression. Every value is a bound parameter.
"""

import csv
import io
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.admin import (
    FeedbackCounts,
    FeedbackItem,
    QueryCount,
    QueryLogAnswer,
    QueryLogDetail,
    QueryLogItem,
    QueryLogPage,
    QueryLogResult,
    StatsDay,
    StatsLang,
    StatsLatency,
    StatsMode,
    StatsRates,
    StatsResponse,
    StatsTotals,
)
from app.schemas.search import SearchFilters
from app.services.query_log import normalise_query

CSV_HEADER = [
    "query_id", "created_at", "query", "lang", "mode", "result_count", "top_article_id",
    "search_ms", "has_answer", "feedback_positive", "feedback_negative", "degraded",
]  # fmt: skip
EXPORT_BATCH = 1000
EXPORT_MAX_ROWS = 200_000
TOP_N = 20

_LIST_COLUMNS = """
    q.query_id, q.created_at, q.query, q.lang, q.mode, q.result_count, q.top_article_id,
    q.search_ms, q.has_answer, q.degraded,
    COALESCE(f.positive, 0) AS positive, COALESCE(f.negative, 0) AS negative
"""
_FEEDBACK_JOIN = """
    LEFT JOIN LATERAL (
        SELECT count(*) FILTER (WHERE rating = 1) AS positive,
               count(*) FILTER (WHERE rating = -1) AS negative
        FROM feedback WHERE feedback.query_id = q.query_id
    ) f ON true
"""


def day_start(day: date) -> datetime:
    """Days are UTC days, in the stats and in the filters."""
    return datetime.combine(day, time.min, tzinfo=UTC)


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _int(value: Any) -> int | None:
    return None if value is None else round(float(value))


def _where(
    q: str | None = None,
    lang: str | None = None,
    mode: str | None = None,
    zero_results: bool | None = None,
    feedback: str | None = None,
    degraded: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = ["true"]
    params: dict[str, Any] = {}
    if q:
        clauses.append("position(:q in q.query_norm) > 0")
        params["q"] = normalise_query(q)
    if lang:
        clauses.append("q.lang = :lang")
        params["lang"] = lang
    if mode:
        clauses.append("q.mode = :mode")
        params["mode"] = mode
    if zero_results is not None:
        clauses.append("q.zero_results" if zero_results else "NOT q.zero_results")
    if degraded is not None:
        clauses.append("q.is_degraded" if degraded else "NOT q.is_degraded")
    if feedback:
        params["rating"] = 1 if feedback == "positive" else -1
        clauses.append(
            "EXISTS (SELECT 1 FROM feedback fb "
            "WHERE fb.query_id = q.query_id AND fb.rating = :rating)"
        )
    if date_from:
        clauses.append("q.created_at >= :date_from")
        params["date_from"] = day_start(date_from)
    if date_to:
        clauses.append("q.created_at < :date_to")
        params["date_to"] = day_start(date_to) + timedelta(days=1)
    return " AND ".join(clauses), params


def _item(row: Any) -> QueryLogItem:
    return QueryLogItem(
        query_id=row.query_id,
        created_at=row.created_at,
        query=row.query,
        lang=row.lang,
        mode=row.mode,
        result_count=row.result_count,
        top_article_id=row.top_article_id,
        search_ms=row.search_ms,
        has_answer=row.has_answer,
        feedback=FeedbackCounts(positive=row.positive, negative=row.negative),
        degraded=list(row.degraded or []),
    )


class AdminService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessionmaker

    # --- statistics -------------------------------------------------------------------------

    async def stats(self, date_from: date, date_to: date) -> StatsResponse:
        params = {"start": day_start(date_from), "end": day_start(date_to) + timedelta(days=1)}
        in_range = "created_at >= :start AND created_at < :end"
        async with self._sessions() as session:
            totals = (
                await session.execute(
                    text(f"""
                        SELECT count(*) AS queries,
                               count(DISTINCT session_hash) AS unique_sessions,
                               count(*) FILTER (WHERE has_answer) AS answers,
                               count(*) FILTER (WHERE zero_results) AS zero_results,
                               count(*) FILTER (WHERE is_degraded) AS degraded,
                               percentile_cont(0.5) WITHIN GROUP (ORDER BY search_ms) AS p50,
                               percentile_cont(0.95) WITHIN GROUP (ORDER BY search_ms) AS p95
                        FROM query_logs WHERE {in_range}
                    """),  # noqa: S608 - fixed SQL fragments, bound parameters
                    params,
                )
            ).one()
            feedback = (
                await session.execute(
                    text(f"""
                        SELECT count(*) FILTER (WHERE rating = 1) AS positive,
                               count(*) FILTER (WHERE rating = -1) AS negative
                        FROM feedback WHERE {in_range}
                    """),  # noqa: S608
                    params,
                )
            ).one()
            ttft = (
                await session.execute(
                    text(f"""
                        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY ttft_ms) AS p50,
                               percentile_cont(0.95) WITHIN GROUP (ORDER BY ttft_ms) AS p95
                        FROM answers WHERE {in_range} AND ttft_ms IS NOT NULL
                    """),  # noqa: S608
                    params,
                )
            ).one()
            by_day = (
                await session.execute(
                    text(f"""
                        SELECT d::date AS day, COALESCE(a.queries, 0) AS queries, a.p95, a.zero_rate
                        FROM generate_series(
                            CAST(:first AS date), CAST(:last AS date), interval '1 day'
                        ) AS d
                        LEFT JOIN (
                            SELECT (created_at AT TIME ZONE 'UTC')::date AS day,
                                   count(*) AS queries,
                                   percentile_cont(0.95) WITHIN GROUP (ORDER BY search_ms) AS p95,
                                   avg(zero_results::int) AS zero_rate
                            FROM query_logs WHERE {in_range} GROUP BY 1
                        ) a ON a.day = d::date
                        ORDER BY 1
                    """),  # noqa: S608
                    {**params, "first": date_from, "last": date_to},
                )
            ).all()
            by_lang = (
                await session.execute(
                    text(f"SELECT lang, count(*) AS n FROM query_logs WHERE {in_range} "  # noqa: S608
                         "GROUP BY lang ORDER BY n DESC, lang"),
                    params,
                )
            ).all()  # fmt: skip
            by_mode = (
                await session.execute(
                    text(f"SELECT mode, count(*) AS n FROM query_logs WHERE {in_range} "  # noqa: S608
                         "GROUP BY mode ORDER BY n DESC, mode"),
                    params,
                )
            ).all()  # fmt: skip
            top = text(f"""
                SELECT query_norm, count(*) AS n FROM query_logs
                WHERE {in_range} AND (NOT :zero_only OR zero_results)
                GROUP BY query_norm ORDER BY n DESC, query_norm LIMIT :limit
            """)  # noqa: S608
            top_all = (
                await session.execute(top, {**params, "zero_only": False, "limit": TOP_N})
            ).all()
            top_zero = (
                await session.execute(top, {**params, "zero_only": True, "limit": TOP_N})
            ).all()

        rated = feedback.positive + feedback.negative
        return StatsResponse(
            date_from=date_from,
            date_to=date_to,
            totals=StatsTotals(
                queries=totals.queries,
                unique_sessions=totals.unique_sessions,
                answers=totals.answers,
                feedback_positive=feedback.positive,
                feedback_negative=feedback.negative,
                zero_result_queries=totals.zero_results,
            ),
            rates=StatsRates(
                zero_result_rate=_rate(totals.zero_results, totals.queries),
                satisfaction_rate=_rate(feedback.positive, rated),
                degraded_rate=_rate(totals.degraded, totals.queries),
            ),
            latency_ms=StatsLatency(
                search_p50=_int(totals.p50),
                search_p95=_int(totals.p95),
                answer_ttft_p50=_int(ttft.p50),
                answer_ttft_p95=_int(ttft.p95),
            ),
            by_day=[
                StatsDay(
                    date=row.day,
                    queries=row.queries,
                    search_p95_ms=_int(row.p95),
                    zero_result_rate=None if row.zero_rate is None else round(row.zero_rate, 4),
                )
                for row in by_day
            ],
            by_lang=[StatsLang(lang=row.lang, queries=row.n) for row in by_lang],
            by_mode=[StatsMode(mode=row.mode, queries=row.n) for row in by_mode],
            top_queries=[QueryCount(query=row.query_norm, count=row.n) for row in top_all],
            top_zero_result_queries=[
                QueryCount(query=row.query_norm, count=row.n) for row in top_zero
            ],
        )

    # --- query log --------------------------------------------------------------------------

    async def list_queries(self, page: int, page_size: int, **filters: Any) -> QueryLogPage:
        where, params = _where(**filters)
        async with self._sessions() as session:
            total = await session.scalar(
                text(f"SELECT count(*) FROM query_logs q WHERE {where}"),  # noqa: S608
                params,
            )
            rows = (
                await session.execute(
                    text(f"""
                        SELECT {_LIST_COLUMNS} FROM query_logs q {_FEEDBACK_JOIN}
                        WHERE {where}
                        ORDER BY q.created_at DESC, q.query_id
                        LIMIT :limit OFFSET :offset
                    """),  # noqa: S608
                    {**params, "limit": page_size, "offset": (page - 1) * page_size},
                )
            ).all()
        return QueryLogPage(
            items=[_item(row) for row in rows], page=page, page_size=page_size, total=total or 0
        )

    async def export_csv(self, **filters: Any) -> AsyncIterator[str]:
        """CSV rows, newest first, read in keyset-paginated batches (no long transaction)."""
        where, params = _where(**filters)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")

        def flush() -> str:
            data = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
            return data

        writer.writerow(CSV_HEADER)
        yield "﻿" + flush()  # BOM: Excel then reads the file as UTF-8
        cursor: tuple[datetime, uuid.UUID] | None = None
        sent = 0
        while sent < EXPORT_MAX_ROWS:
            page_where, page_params = where, dict(params)
            if cursor is not None:
                page_where += " AND (q.created_at, q.query_id) < (:cursor_at, :cursor_id)"
                page_params.update(cursor_at=cursor[0], cursor_id=cursor[1])
            async with self._sessions() as session:
                rows = (
                    await session.execute(
                        text(f"""
                            SELECT {_LIST_COLUMNS} FROM query_logs q {_FEEDBACK_JOIN}
                            WHERE {page_where}
                            ORDER BY q.created_at DESC, q.query_id DESC LIMIT :limit
                        """),  # noqa: S608
                        {**page_params, "limit": EXPORT_BATCH},
                    )
                ).all()
            if not rows:
                break
            for row in rows:
                writer.writerow(
                    [
                        row.query_id,
                        row.created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        row.query,
                        row.lang,
                        row.mode,
                        row.result_count,
                        row.top_article_id or "",
                        "" if row.search_ms is None else row.search_ms,
                        str(row.has_answer).lower(),
                        row.positive,
                        row.negative,
                        " ".join(row.degraded or []),
                    ]
                )
            sent += len(rows)
            cursor = (rows[-1].created_at, rows[-1].query_id)
            yield flush()

    async def get_query(self, query_id: uuid.UUID) -> QueryLogDetail | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    text(f"""
                        SELECT {_LIST_COLUMNS}, q.filters, q.top_k, q.results, q.timing_ms,
                               q.pipeline_version, q.session_hash
                        FROM query_logs q {_FEEDBACK_JOIN}
                        WHERE q.query_id = :query_id
                    """),  # noqa: S608
                    {"query_id": query_id},
                )
            ).one_or_none()
            if row is None:
                return None
            answer = (
                await session.execute(
                    text("""
                        SELECT answer_id, text, citations, grounded, search_ms, ttft_ms, total_ms
                        FROM answers WHERE query_id = :query_id
                    """),
                    {"query_id": query_id},
                )
            ).one_or_none()
            feedback = (
                await session.execute(
                    text("""
                        SELECT target, article_id, rating, comment, created_at
                        FROM feedback WHERE query_id = :query_id ORDER BY created_at, id
                    """),
                    {"query_id": query_id},
                )
            ).all()

        item = _item(row)
        timing = {k: v for k, v in (row.timing_ms or {}).items() if isinstance(v, int)}
        return QueryLogDetail(
            **item.model_dump(),
            filters=SearchFilters.model_validate(row.filters or {}),
            top_k=row.top_k,
            results=[
                QueryLogResult(
                    rank=r["rank"],
                    article_id=r["article_id"],
                    title=r.get("title"),
                    doc_short_title=r.get("doc_short_title"),
                    score=r.get("score", 0.0),
                )
                for r in (row.results or [])
            ],
            timing_ms=timing,
            answer=None
            if answer is None
            else QueryLogAnswer(
                answer_id=answer.answer_id,
                text=answer.text,
                citations=list(answer.citations or []),
                grounded=answer.grounded,
                timing_ms={
                    k: v
                    for k, v in (
                        ("search", answer.search_ms),
                        ("ttft", answer.ttft_ms),
                        ("total", answer.total_ms),
                    )
                    if v is not None
                },
            ),
            feedback_items=[
                FeedbackItem(
                    target=f.target,
                    article_id=f.article_id,
                    rating=f.rating,
                    comment=f.comment,
                    created_at=f.created_at,
                )
                for f in feedback
            ],
            pipeline_version=row.pipeline_version,
            session_hash=row.session_hash,
        )
