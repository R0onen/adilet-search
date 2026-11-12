# Status: Frontend agent

_Last updated: 2026-11-12 · FE-04 admin panel and feedback (branch `fe/04-admin`)_

## Current phase
The presentation MVP (search, streamed answer, article drawer, comparison page) is merged. **FE-04 is implemented on this branch:** the admin panel on the BE-04 API, and feedback buttons on the public pages. Next: FE-06 (production image, more tests) and FE-07 (demo, docs).

## Done in FE-04
- **Admin panel** at `/admin`, lazy-loaded (10.9 KB gzip of JS, its own CSS; not in the public bundle):
  - login with validation and messages for `401` and `429`; route guard that returns the user to the page they asked for; any `401` logs out;
  - dashboard: date range in the URL, 8 KPI tiles (search p95 coloured against the 2 s target), 2 line charts, 2 bar lists, top queries and top zero-result queries linking into the log;
  - query log: URL-synced filters and pagination, detail drawer, CSV export;
  - system: component health with auto-refresh, models, index state with a "reindex required" banner, reindex dialog with job progress and the `409` message.
- **Charts** are small inline SVG components with text alternatives; no chart library was added.
- **Public pages:** 👍 / 👎 on results and on the answer (`POST /feedback`), a rate-limit message with the wait time, `/?article=<id>` opens an article directly.
- **Types** regenerated from `contracts/openapi.json`.
- **Mocks:** `src/mocks/admin.ts` serves the admin API in mock mode (login `admin` / `demo`).

## Verified
- `npm run lint`, `npm run build` (strict typecheck) and 20 unit tests pass. New tests: KPI thresholds and formatting, the auth guard and return-after-login, `429` on login, logout on `401`, dashboard → filtered log → detail drawer, the reindex flow with progress and the `409`.
- Live check in a browser against the real backend (pipeline 0.2.0): the dashboard, the query log and the system page show real data; the system page followed a real reindex job started through the API.
- **Not run in this phase:** the Playwright e2e suite and axe scans (they cover the public pages and were last run for the MVP).

## Next steps
- FE-06: production image behind the reverse proxy, e2e for the admin flow, bundle check.
- A Kazakh speaker should review the KK UI strings, including the new feedback strings.

## Blockers (need a human)
- None.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| Backend | None open. The `503` → `200 degraded` change and the rate limits from BE-04 are handled. | 2026-11-12 | done |

## Notes for others (routes, how to run)
- Start: `cd frontend && npm ci && npm run dev` → `http://127.0.0.1:5173` (mock mode).
- Live mode: `VITE_API_MODE=live npm run dev`; Vite proxies `/api` to `API_PROXY_TARGET` (default `http://127.0.0.1:8000`).
- Routes: `/`, `/compare`, `/about`, `/admin`, `/admin/queries`, `/admin/system`, `/admin/login`.
