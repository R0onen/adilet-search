# FE-06: Testing and production build (week 6)

**Goal:** the frontend is tested end to end and ships as a production image that Backend can deploy behind Caddy.

## Tasks

1. **Unit and component tests** (Vitest + Testing Library). Bring coverage of `src/features` and `src/api` to ≥ 70% (lines), with the report in CI. Focus on the logic: the SSE parser, citation handling, URL state, the error mapping, formatters, the auth guard.

2. **E2E tests** (Playwright). Every scenario runs in two modes:
   - **CI on MSW:** the default, deterministic;
   - **live**, with `E2E_BASE_URL` pointing at the dev stack or the deployed URL; tagged `@live`; run manually and before the demo.

   Scenarios:
   1. search RU → results → article → back keeps the state;
   2. search KK → KK results → RU↔KK switch on the article;
   3. filters + URL share/reload;
   4. answer streaming → citation [1] → the correct article; stop/regenerate;
   5. feedback on a result and on the answer;
   6. the compare page with a preset query;
   7. admin: login → dashboard → zero-result query → detail drawer → CSV export starts;
   8. admin: system page → reindex dialog (MSW only; never trigger a real reindex in a live e2e run);
   9. a degraded banner (MSW variant);
   10. a 404 page.

   Add `@axe-core/playwright` checks on the main routes. Capture screenshots on failure.

3. **Production image: `frontend/Dockerfile`.**
   - Multi-stage: a node build, then `nginxinc/nginx-unprivileged` serving `dist/` on port 8080.
   - SPA history fallback to `index.html`.
   - Long-cache headers for hashed assets, `no-cache` for `index.html`; gzip.
   - No runtime API config is needed: the API is same-origin `/api/v1` via Caddy.
   - A healthcheck.
   - Give Backend the compose service snippet and the CSP needs (e.g. `connect-src 'self'`, no inline scripts) through your status file.

4. **CI.** Give Backend your exact commands for the frontend CI job: `npm ci`, `gen:api` + git diff check (types in sync with `openapi.json`), lint, typecheck, unit tests, build, Playwright on MSW.

5. **Pre-demo check:** run the `@live` e2e suite against the deployed URL once BE-06 is done, and record the result in the status file.

## Acceptance criteria

- [ ] CI is green with the frontend job, and coverage ≥ 70% on features/api.
- [ ] All 10 e2e scenarios pass on MSW. The `@live` suite passes against the deployed URL (or the failures are reported to the right owner).
- [ ] The production image builds, serves the SPA on 8080, and deep links (`/article/...`, `/admin/...`) work after a reload behind Caddy.
