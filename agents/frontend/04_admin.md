# FE-04: Admin panel (week 4)

**Goal: G3.** An administrator can see how the search is used and how well it performs, find the queries where it fails, and check or refresh the system. All of it works on real data from BE-04.

The admin UI is Russian-first; English is acceptable for technical labels.

## Tasks

1. **Auth.**
   - `/admin/login`: a form with validation and an error message for 401/429.
   - The JWT is kept in memory, mirrored to sessionStorage so it survives a reload; it is cleared on logout and on expiry.
   - A route guard redirects to the login page. Any 401 from an admin call logs the user out and returns them to the page they were on after re-login.
   - Admin routes are lazy-loaded and kept out of the public bundle.

2. **Dashboard: `/admin`.**
   - **Date range:** 7 days / 30 days / custom, kept in the URL.
   - **KPI tiles:**
     - total queries; unique sessions; answers generated;
     - **search p95** against the 2 s target (green ≤ 1.5 s, amber ≤ 2 s, red > 2 s);
     - zero-result rate; satisfaction rate (show "—" when it is null); degraded rate.
   - **Charts** (Recharts, accessible, with empty states):
     - queries per day (line);
     - search p95 per day with a reference line at 2000 ms;
     - the language split (bar); the mode split (bar).
   - **Tables:** top queries; **top zero-result queries** (labelled «Пробелы в базе / непонятые запросы»). Clicking a row opens the query log filtered to that query.

3. **Query log: `/admin/queries`.**
   - A server-paginated table with columns: time, query, language, mode, result count, search ms, answer ✓, feedback (👍 n / 👎 n), degraded.
   - **Filters**, kept in the URL: text, language, mode, zero results only, negative feedback only, degraded only, date range.
   - **The row detail drawer** (`GET /admin/queries/{id}`):
     - the query and its filters;
     - the ranked results with scores and links to the articles;
     - a timing breakdown as a stacked bar (embed / retrieve / fuse / rerank);
     - the answer text with its citations and timings;
     - feedback items with comments;
     - the pipeline version.
   - **Export CSV** downloads `/admin/queries/export` with the current filters.

4. **System: `/admin/system`.**
   - Component health (database, Qdrant, ML service, LLM) with status dots and a last-checked time. It auto-refreshes every 30 s.
   - Pipeline and models: the version, embedder, reranker, generator, `index_compat_id`.
   - The index: alias → collection, points, documents, articles, compatibility (a red banner «Требуется переиндексация» when it is false).
   - **Reindex:**
     - a confirm dialog that explains the impact (no downtime; the old index serves until the switch);
     - source `processed`/`sample`; "use precomputed embeddings";
     - then poll `GET /admin/jobs/{id}` every 2 s, with a progress bar and message;
     - success and failure states; 409 → «Переиндексация уже выполняется».
   - A link to Grafana (`/grafana/`).

5. **Tests:**
   - the auth guard and the 401 handling;
   - KPI colour thresholds;
   - URL-synced filters and pagination;
   - the drawer rendering from fixture detail;
   - the reindex flow with mocked job progress, including the 409;
   - e2e on mocks: login → dashboard → click a zero-result query → filtered log → open the detail.

## Acceptance criteria (G3)

- [ ] Against the live stack (after a short load test so there is data), the dashboard numbers match `GET /admin/stats` and the drawer matches the DB rows. Spot-check 3.
- [ ] During the degraded drill (Backend stops `ml-service`), the system page shows `ml_service: down` within 30 s and recovers afterwards.
- [ ] Admin code is not in the public entry chunk (check the bundle analysis).
