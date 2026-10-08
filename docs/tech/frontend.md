# Frontend MVP

See [`frontend/README.md`](../../frontend/README.md) for setup, live integration, and validation commands.
See [`demo_script.md`](../presentation/demo_script.md) for a three-minute presentation flow.

## Data flow

`SearchForm` constructs generated `SearchRequest` types. TanStack Query calls `src/api/client.ts`,
which uses openapi-fetch and generated OpenAPI paths. The client includes an anonymous session ID.
Search responses render as source cards. `AnswerPanel` invokes the POST-SSE helper independently
and resolves citation numbers against that stream's `sources` payload. Final `done.text` replaces
the incremental text. AbortController stops the stream on cancellation or unmount.

`ArticleDrawer` loads the article by ID, preserves its text, displays status/revision metadata,
and follows `parallel_article_id` for RU/KK switching. A live article's http(s) source URL opens
in a new tab. Synthetic fixtures deliberately have no external article link.

## Modes and failure handling

`VITE_API_MODE=mock` starts the MSW browser worker before mounting React; it is the default.
`live` uses same-origin API routes without starting the worker. The Vite dev proxy target is
configured by `API_PROXY_TARGET`. Switching modes requires restarting Vite.

Search failure, empty search, degraded stages, answer failure, ungrounded answers, cancellation,
and article failure are represented explicitly. A failed answer leaves source cards intact.
There is no automatic live-to-mock fallback. Contract changes belong to the backend owner.

## Validation boundaries

Automated checks cover strict typing, lint, SSE framing/UTF-8/reader cleanup, deterministic mock
filters and language selection, browser presentation flow, 360px layout, accessibility scans,
empty/error states, and answer interruption/failure. These do not measure backend integration,
model quality, public deployment, p95 latency, or production LCP. See frontend status for results.

Mock search and answers are intentionally synthetic. Until the ML-owned sample corpus is released,
fixtures are copied verbatim from the backend development corpus. The UI and comparison explicitly
identify this limitation. All Kazakh UI keys are provisional pending human review.
