# Adilet Search frontend

Presentation MVP: question → search → streamed answer → citation → bilingual article.
Includes a keyword/hybrid comparison view and RU/KK/EN UI. Russian is the default.

## Start the reliable local demonstration

From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. If dependencies are already installed, only `npm run dev` is needed.
Mock mode is the default and needs no Docker, backend, model, API key, or internet after installation.
Use this origin rather than opening `index.html` directly: MSW needs a localhost service worker.
The port is fixed so a conflict fails visibly rather than silently changing the demo URL.

**This is a frontend demonstration, not a trained AI system.** The visible banner identifies
synthetic data and scripted answers. Fixtures are verbatim copies of the synthetic texts in
`backend/dev/sample_corpus.py`, with matching `T000000000*` IDs. They are not real legislation.
MSW serves contract-shaped requests; hybrid demo ranking uses explicit topic rules, while
keyword ranking uses substring matches. The comparison is not an evaluation of a real model.
No invented latency or quality metrics are shown. Synthetic articles have no real Adilet article
URL, so mock article drawers do not offer a misleading external source link.

## Connect the backend

Create `frontend/.env.local`:

```dotenv
VITE_API_MODE=live
API_PROXY_TARGET=http://127.0.0.1:8000
```

Restart Vite. Requests use same-origin `/api/v1/*`; Vite proxies them to the configured backend.
The page shows **Live API**, and MSW is not started. Network failures remain visible, with no
automatic substitution of demo data. Remove `.env.local` or set `VITE_API_MODE=mock`, then restart
to return to the reliable demonstration. These variables contain no credentials.

The last backend status lists `/search`, `/documents`, and `/articles/{article_id}` as implemented;
`/answer` is still a 501 stub. Live search can therefore work before AI answers do. Answer errors
preserve search results and article access. `/documents` populates the document filter in both modes.
Real data and actual models must be provided by the backend/AI teammates.

## Verify

```powershell
npm run gen:api
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

Browser tests use installed Microsoft Edge through Playwright (`channel: 'msedge'`). On another
machine, install Edge or change the channel to an installed Playwright Chromium browser.
Tests start a mock dev server automatically. Stop any live-mode dev server first.
Screenshots are saved in `docs/presentation/img/` by the presentation journey.

For a production-build local preview: `npm run build`, then `npm run preview` (port 4173).
Preview serves static files; it does not provide the live API dev proxy. A deployment must
reverse-proxy `/api/v1` and return `index.html` for SPA routes. No deployment is included here.

## Implementation

- React + Vite + strict TypeScript, Tailwind, local shadcn-style button, Radix accessible dialog.
- React Router, TanStack Query, i18next; comparison route and mock worker are loaded separately.
- Generated `src/api/schema.d.ts` comes from `contracts/openapi.json`. Regenerate after schema changes.
- Typed calls use the schema's full `/api/v1/...` paths. All network calls are confined to `src/api/`.
- POST-SSE handles chunked UTF-8, CR/LF framing, sources, tokens, authoritative done text,
  errors, incomplete streams, and cancellation. React renders answer text safely without raw HTML.
- Citations resolve against the SSE source list, not search result positions.
- Article text preserves whitespace and numbering. Radix provides focus trapping and Escape to close.
- Session and language persistence tolerate unavailable localStorage.

Admin, authentication, feedback UI, Docker image, exhaustive test coverage, and deployed performance
are deferred. Kazakh UI strings and inherited synthetic Kazakh texts require human language review.
API models are generated, not handwritten; runtime payload validation remains a backend responsibility.
