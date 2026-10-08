# Status: Frontend agent

_Last updated: 2026-10-08 · same-day presentation MVP_

## Current phase
Presentation MVP combines the critical parts of FE-01/02/03/05/06/07. Full phase gates are not claimed.

## Done
- React/Vite/strict TypeScript frontend, Tailwind styling, Radix article drawer, RU/KK/EN i18n.
- Generated API types from `contracts/openapi.json`, typed search/documents/articles, isolated API layer.
- Search filters, source metadata, POST-SSE answer streaming, source-resolved citations, cancellation.
- RU/KK article switching; lazy keyword/hybrid comparison route; responsive 360px layout.
- Explicit mock/live modes. Mock fixtures copy the backend synthetic corpus verbatim; not real law.
- Build/lint/unit/browser checks, screenshots, frontend README, technical handoff, demo script.

## In progress
- None for the presentation MVP.

## Next steps
- Rehearse the three-minute demo in `docs/presentation/demo_script.md`.
- Connect and validate the actual backend/model stack when ready; record a backup video.
- Full admin, feedback UI, deployment image, expanded tests, and remaining phase gates are deferred.

## Blockers (need a human)
- No blocker for the local synthetic frontend demo.
- Real corpus/model and live `/answer` are needed for a genuine end-to-end AI demonstration.
- A Kazakh speaker must review all provisional KK UI keys in `frontend/src/i18n.ts` and inherited synthetic KK text.

## Requests to other agents
| To | Request | Since | Status |
|---|---|---|---|
| Backend | Types regenerated after BE-03; UI handles CRLF/LF, heartbeat comments, sources/tokens/authoritative done, JSON errors and SSE failures. Live integration remains to be rehearsed. Admin coverage is deferred. | 2026-10-08 | FYI |
| ML | Supply real sample articles and real pipeline; current demo uses synthetic backend fixtures and scripted answers, clearly labelled. | 2026-10-08 | open |

## Notes for others (routes, how to run, contract mismatches found)
- Start: `cd frontend`, `npm ci`, `npm run dev`; URL `http://127.0.0.1:5173`.
- API mode: mock by default. `frontend/.env.local`: `VITE_API_MODE=live`; restart Vite.
- Proxy: `API_PROXY_TARGET=http://127.0.0.1:8000`; network errors never silently fall back to mocks.
- Mock `/answer` streams scripted text; `/error`, `/answer-error`, `/stream-error` support failure drills.
- No API contract mismatch found; generated types mark some documented fields optional, handled defensively.
- Frontend changes only; backend/ML-owned files are unchanged by this PR. Branch `fe/presentation-mvp` is based on the fetched `origin/main` including BE-03 and the updated agent briefs. Commit/push/PR authorized by the user; no deployment or merge.

## Validation
- `npm run gen:api`, production build (includes strict typecheck), lint, and 12 unit tests passed after updating to BE-03. Answer lifecycle tests include JSON 422/503, SSE failure after sources, authoritative final text, and incomplete streams.
- 4 Edge/Playwright scenarios passed: complete presentation journey, empty/error search, 360px Kazakh layout, answer cancellation/501/SSE failure with preserved sources.
- Axe scans passed for the RU home, completed result screen, and 360px KK results. These are automated scans, not a complete WCAG certification.
- Screenshots: `docs/presentation/img/frontend-{home,results,compare,mobile}.png`.
- Read-only local backend probe at `127.0.0.1:8000/api/v1/health` was refused. Live integration is unverified.
- Current build: main app about 144 KB gzip; demo worker/data chunk about 163 KB gzip, loaded only for mocks. Total mock startup JS slightly exceeds the 300 KB target; production LCP is unmeasured.
