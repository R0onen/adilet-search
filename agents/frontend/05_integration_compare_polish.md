# FE-05: Live integration, compare page, polish (week 5)

**Goal: G4.** The UI works fully against the live stack with the v1.0.0 models. The compare page makes the value of the project obvious in 10 seconds. The app meets the quality bar in the brief.

## Tasks

1. **Live integration pass.**
   - Run with `VITE_API_MODE=live` against `docker compose up` (with real `ml-service`).
   - Go through every screen and state:
     - search in all three modes;
     - filters;
     - KK queries;
     - answer streaming, stop and regenerate;
     - articles with the RU↔KK switch;
     - feedback;
     - every admin page;
     - degraded mode (ask the human to stop `ml-service`).
   - **Contract mismatches:** report them to Backend (status file + human) with the endpoint, field, expected vs actual, and the contract section. Do not patch types locally. Regenerate the types after Backend's fix.

2. **The compare page: `/compare?q=…`** (the demo centrepiece).
   - **Columns:** «Поиск по ключевым словам» (`mode=keyword`, a stand-in for today's search) vs «Интеллектуальный поиск» (`mode=hybrid`). An optional third column, `semantic`, can be toggled on.
   - **Requests:** the columns run in parallel; each column shows its own timing.
   - **Comparison cues:**
     - articles that appear in both columns get a matching colour or link line;
     - the position of the "best" article (the smart top-1) is marked in the keyword column, or "not in top 10".
   - **Preset demo queries** where keyword search visibly fails. Ask ML (status-file request) for 5 queries from `final_eval`/`eval_api` where `keyword` misses and `hybrid` hits. Until those arrive, use the TOR examples.
   - **"Open in normal search"** carries the query over.
   - **Sharing:** the URL is shareable, so the presenter can pre-load tabs.

3. **Polish.**
   - **i18n:** finish `ru`/`kk`/`en`. A human Kazakh speaker reviews the `kk` strings; apply their fixes and clear the "unreviewed" list.
   - **Responsive:** check 360/768/1280/1920 px. The filters drawer and the citation previews must work on touch.
   - **Accessibility:**
     - run an axe check on every route (no serious or critical violations);
     - the keyboard path through search → result → article → back;
     - visible focus;
     - live-region announcements for "results loaded" and "answer finished";
     - `prefers-reduced-motion` respected.
   - **Performance:**
     - check the route-level code splitting;
     - add a bundle analysis report (rollup-plugin-visualizer);
     - initial JS ≤ 300 KB gzip;
     - images and fonts optimised;
     - Lighthouse on the production build: Performance ≥ 90, Accessibility ≥ 95.
   - **Details:** favicon, page titles per route (`document.title` with the query), meta description, a 404 page, an error boundary with a reload action, an offline/network-error toast.

4. **Optional stretch, only if everything above is done:** an embeddable search widget for the Legal Service site. It is a web component in a separate small build (`<adilet-search-widget api-base="…">`) that shows a search box + results linking to our article pages. Document it for Backend's integration guide.

## Acceptance criteria (G4)

- [ ] Every flow works on the live stack with v1.0.0. The mismatch list is empty or the remaining items are assigned to someone.
- [ ] The compare page shows at least 3 convincing preset queries.
- [ ] axe reports no serious or critical issues. The Lighthouse scores and bundle size are recorded in the status file.
- [ ] The `kk` UI strings have been reviewed by a human.
