# FE-01: Scaffold, API layer, mocks, app shell (week 1)

**Goal: G0.** The app shell runs on mocks, the typed API layer and MSW cover the whole contract, and the build, lint and tests are green.

## Tasks

1. **Scaffold** `frontend/` with Vite (React + TS strict), Tailwind, shadcn/ui, ESLint + Prettier, Vitest + Testing Library, and Playwright (an empty smoke test). Use this structure:

   ```
   frontend/src/
     api/          client.ts (openapi-fetch), sse.ts, schema.d.ts (generated), errors.ts, session.ts
     mocks/        handlers/*.ts, fixtures/*.ts, browser.ts, node.ts
     features/     search/, answer/, article/, compare/, admin/
     components/   ui/ (shadcn), layout/, common/
     pages/        route components
     i18n/         index.ts, ru.json, kk.json, en.json
     lib/          utils, formatters (dates, citations), url-state
     styles/
   ```

2. **API layer.**
   - `npm run gen:api` runs openapi-typescript on `../contracts/openapi.json` and writes `src/api/schema.d.ts`. If the file isn't there yet (Backend creates it in BE-01), use `types.tmp.ts` and record that in your status file.
   - `client.ts`: an openapi-fetch client with base URL `/api/v1`. It adds `X-Session-Id` (a random UUID kept in localStorage under `adilet_session_id`; it must work when storage is unavailable) and turns every error into the contract error type, with a typed `ApiError`.
   - `sse.ts`: a typed POST-SSE helper for `/answer`. It has `onSources`, `onToken`, `onDone` and `onError` callbacks and supports `AbortController` cancellation. **It must handle events split across network chunks, and both `
` and `
` line endings** (the backend's sse-starlette sends `
`). It must ignore `: ping` heartbeat comments (sent every 15 s). Validation (422) and search (503) errors arrive as plain JSON before any stream opens; map them to `ApiError`.

3. **MSW mocks** for every endpoint in `contracts/api.md`, with realistic fixtures:
   - articles from `data/sample/sample_articles.json`, mapped into the API shapes;
   - search results for the three TOR queries + one KK query;
   - an `/answer` stream (sources → tokens at ~30 ms → done) plus an error variant;
   - admin stats covering 14 days;
   - a paginated query log;
   - system status.

   Mocks start only when `VITE_API_MODE=mock`, which is the default in development until the backend is up.

4. **App shell.**
   - A header with the "Adilet Search" wordmark, a language switcher (RU / ҚАЗ / EN, persisted) and an admin link.
   - A footer with the disclaimer and a "Source: adilet.zan.kz" note.
   - Routes: `/`, `/search`, `/article/:articleId`, `/compare`, `/admin/login`, `/admin`, `/admin/queries`, `/admin/system`, and a 404.
   - Lazy-load the admin and compare routes. Add an error boundary.

5. **i18n:** i18next with `ru` as the default and fallback. All shell strings go through keys.

6. **Design tokens:** colours (taken from the customer's site palette), typography (a readable serif or sans for legal text, with a comfortable line length), spacing, and status-badge colours (in force / repealed / excluded).

## Acceptance criteria (G0)

- [ ] `npm run dev` on mocks shows the shell, routes and language switch. `npm run build`, `npm run lint`, `npm run typecheck` and `npm test` all pass.
- [ ] Unit tests for `sse.ts` cover: an event split across chunks, several events in one chunk, `
` line endings, a `: ping` comment, `error` after `sources`, a JSON 422/503 instead of a stream, and abort.
- [ ] The status file lists the commands, env vars and any open questions about the contract.
