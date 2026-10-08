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
- Replace bootstrap retrieval/generation and teaching corpus before claiming real legal AI; record a backup video.
- Full admin, feedback UI, deployment image, expanded tests, and remaining phase gates are deferred.

## Blockers (need a human)
- No blocker for the local synthetic frontend demo.
- Live `/answer` is verified with the bootstrap pipeline. Real corpus/model are still needed for a genuine legal AI demonstration.
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
- Local full-stack deployment on main `99ffde9` passed live API and Edge browser smoke checks: RU/KK search (10 results each), SSE sources/tokens/done with resolved citations, article drawer and RU/KK switching, and comparison including the keyword empty state. No browser page errors occurred.
- All four Docker services are healthy; migrations and indexing completed (2 document-language rows, 30 articles, 33 chunks). This verifies integration, not model accuracy: RU salary nonpayment ranks article 115 about deductions first and the fallback answer repeats it. Keyword search returns no matches for that example.
- Pipeline `0.1.0-bootstrap` uses hash embeddings, lexical ranking, and extractive fallback, with paraphrased teaching text under real Labor Code IDs. It has no running LLM, and its text must not be represented as official legislation. Ecology is not covered by the sample.
- Current build: main app about 144 KB gzip; demo worker/data chunk about 163 KB gzip, loaded only for mocks. Total mock startup JS slightly exceeds the 300 KB target; production LCP is unmeasured.

## Local integrated deployment (2026-10-08)
- Isolated Compose project `adilet-localtest` uses ignored `.env.localtest` and separate database volumes. Existing projects were not stopped or removed.
- Frontend: `http://127.0.0.1:5173`; backend docs: `http://127.0.0.1:18000/api/v1/docs`; ML: `http://127.0.0.1:18001/health`.
- Start services from repository root: `docker compose -p adilet-localtest --env-file .env.localtest --profile ml up -d --wait`.
- Start UI from `frontend` in PowerShell: `$env:VITE_API_MODE='live'; $env:API_PROXY_TARGET='http://127.0.0.1:18000'; npm run dev`.
- Stop only this stack, retaining data: `docker compose -p adilet-localtest --env-file .env.localtest --profile ml stop`. Stop the frontend with Ctrl+C in its terminal.
- Local evidence (ignored): `frontend/test-results/live-report.json`, `live-results.png`, `live-compare.png`, and `localtest-build.log`. First build needed a retry after a network/DNS download failure.
- This is a local development deployment; public hosting and a frontend production image remain unverified.

## Live Groq and official demo corpus (2026-10-08; supersedes bootstrap runtime notes above)
- User explicitly requested external free-API integration and usable demo articles. Configured the existing OpenAI-compatible generator for Groq `openai/gpt-oss-120b` using ignored `.env.localtest`; no dependency or backend/ML source change. Key is server-side only. The engine appends `/v1/chat/completions`, so base is `https://api.groq.com/openai`.
- Replaced only the isolated local runtime corpus with official Adilet Labor Code articles 68/88/113 in RU/KK: 2 document-language rows, 6 articles, 6 chunks. Original committed bootstrap sample is unchanged. Local corpus and provenance are preserved in ignored `data/processed/demo-official/`; restore/index commands are in `docs/presentation/demo_script.md`.
- Added reproducible extraction helper `frontend/scripts/build-official-demo.py` (run in the existing ML container) and live-only UI example questions matching covered topics. Mock example behavior remains unchanged. The short source title flags the three-article demo snapshot; unknown revision dates are null.
- Verified six RU/KK retrieval questions rank their expected official article first. Four real Groq answers passed source-fact and citation checks (RU hours, leave, salary timing; KK hours). Observed individual completion times about 1.2–1.4 s. Citation validity does not establish general answer accuracy; annual-leave exceptions should be shown in the full source.
- Verified Edge live answer from the new example button, citation drawer, official source link, Kazakh switch and comparison; no browser page errors. Build, lint, 12 unit tests and diff check passed. Evidence is in ignored `frontend/test-results/`.
- All four services healthy and left running; UI at http://127.0.0.1:5173. Backend answer limit is at most 1024 tokens, enforced by Settings; corrected local configuration after an initial invalid 2048 setting.
- Remaining: search still uses bootstrap hash/BM25/lexical ranking; no semantic quality or load benchmark claimed. Groq needs internet and is rate-limited. Larger corpus, genuine semantic embedder, public hosting, backup video and human KK review remain separate work.
- ML/Backend handoff: adopt reviewed official snapshots into your owned corpus pipeline; current local dataset has no claimed revision date. Manifest still says `0.1.0-bootstrap` even though generator is now Groq; future versioned manifests should distinguish retrieval and generation. No contract change, commit, push or PR in this phase.

## Expanded official baseline and diagnostics (2026-10-08)
- User requested more official sources and testing of varied/difficult questions; user explicitly chose to keep existing dependencies. No dependency, ML/backend source, contract or model-manifest change.
- Added presentation tools in `frontend/scripts/`: `build_official_baseline.py`, `test_official_baseline.py`, `evaluate-baseline.mjs`. Ingestion supports cached/offline operation, respects robots on uncached fetches, paces requests, scopes parsing to the statute, preserves inline source text and real anchors, separates fragmented amendment notes, rejects ambiguous/empty extraction and creates bounded exact-slice chunks.
- Local isolated stack now indexes the full extracted Labor and Environmental Codes in RU/KK: 653 article IDs, 1,306 article-language rows, 2,799 chunks, four document-language rows. Eighteen removed article-language rows are marked excluded and filtered from default search. Revision dates and legal effective-date resolution remain unverified. Raw HTML, timestamps, hashes and dataset quality are saved in ignored `data/processed/official-baseline/`.
- Existing sample and three-article dataset preserved. Indexer validation/upsert/alias switch succeeded; prior Qdrant collections retained. The local chunking variant is `demo-char1400-v1`, explicitly recorded in dataset metadata; production manifest alignment is an ML handoff.
- Validation: four parser regressions passed; backend corpus validation/index passed; six RU/KK direct query checks and Edge source drawer/KK switch passed; lint and diff check passed; all four services healthy. No build rerun needed for tooling/docs-only changes.
- Original diagnostic set: 13 supported cases plus two unsupported questions; inferred source labels, not a gold benchmark. All required sources in top five for 8/13, top ten for 9/13. Five live Groq answer checks exposed missing-source refusal, incorrect overtime-consent inference, incorrect leave-recall exception wording, one unexplained generation-unavailable event and a refusal marked grounded because of citation/refusal-phrase limitations. These are failures, not presentation-quality passes.
- See `docs/presentation/qa_frontend.md` for exact reproduction commands, diagnostic questions, source ranks and handoff. `demo_script.md` now flags the larger baseline and limitations. App remains at http://127.0.0.1:5173. No commit/push/deploy outside the existing local stack.
- Requests to ML: tighten the actual serving prompt against inference from absent rules; evaluate dependency-free Groq query decomposition/terminology expansion with caching/quotas; eventually replace hash embeddings/lexical reranking when dependencies are authorized. Source context should select relevant passages rather than only the beginning of each article.
- Requests to Backend: distinguish citation reference validity from evidence support; improve refusal detection (VAT refusal with citations was marked grounded) and expose upstream generator failure status safely. Ownership boundaries in CLAUDE.md are preserved; these changes require the respective owners.

## Presentation guide and live rehearsal (2026-10-08)
- Replaced the historical three-article demo script with a current, moderate-length speaking/demo guide in `docs/presentation/demo_script.md`: local URLs, project purpose, plain-language RAG/architecture explanation, corpus scope, frontend contribution, four-minute walkthrough, professor Q&A, limitations and restart commands.
- Current app/frontend and backend health endpoints returned HTTP 200; all four Docker services healthy. No service restart or reindex was necessary; local deployment remains at http://127.0.0.1:5173.
- Fresh live Edge rehearsal passed generated annual-leave answer, source-button opening, official article content, KK switch and comparison; no page errors. Screenshot refreshed at ignored `frontend/test-results/groq-live-answer.png`.
- The preceding strict citation check failed because the model emitted nonstandard citation notation (e.g. corner brackets), so inline citations were not clickable and the answer was marked ungrounded. The guide explicitly uses separate source buttons and does not claim robust citation formatting. No application code was changed for this request.
- Documentation diff check passed; no build/tests rerun for documentation-only edits. Guide/style reference lookup returned no suitable writing examples, so wording uses the user's conversational context without claiming a retrieved style match. No new commit or push.
