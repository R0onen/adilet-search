# FE-07: Demo script, documentation, slides (week 6)

**Goal:** a demo that goes smoothly even if something breaks, plus the UI documentation and the frontend part of the final presentation.

## Tasks

1. **Demo script: `docs/presentation/demo_script.md`** (3–4 minutes, timed, with exact URLs and queries):
   1. **The problem (30 s).** The compare page with a preset query: keyword search misses, smart search finds the right article.
   2. **Smart search (45 s).** A plain RU question → results with sources, status and revision date; open an article.
   3. **AI answer (45 s).** It streams with citations; click [1] → the exact article; point out the disclaimer and the "grounded" behaviour on an unanswerable question.
   4. **Kazakh (30 s).** A KK query → KK results → the RU↔KK switch.
   5. **Operations (45 s).** The admin dashboard (p95 against 2 s, zero-result queries) → a query detail → the system page → Grafana.

   Plus:
   - **Pre-flight checklist:** the URL is up, the health check is ok, the LLM is warmed up (send one query 5 minutes before), the browser zoom, the tabs pre-loaded, the admin logged in, notifications off.
   - **Plan B if the network or server fails:** the local `docker compose` stack, then the mock mode build (`VITE_API_MODE=mock`), then the recorded video.

2. **Backup video.** A 3–4 minute screen recording of the script on the deployed system, plus PNG screenshots of each step in `docs/presentation/img/`. Ask the human to record it if you can't; give them the exact steps.

3. **`docs/tech/frontend.md`:**
   - the architecture: routes, feature folders, state (TanStack Query + URL state), the API layer and type generation, the SSE handling;
   - mocks;
   - i18n;
   - how to run, test and build;
   - accessibility and performance results;
   - how to add a new endpoint (the contract → `gen:api` → client → MSW handler).

4. **`docs/user_guide.md`** (in Russian, short, with screenshots):
   - how to search, filters, the modes;
   - how to read an AI answer and check its sources;
   - feedback;
   - for administrators: the dashboard, the query log, reindex.

5. **Presentation sections: `docs/presentation/sections/frontend.md`** (Marp):
   - **slide 8, Demonstration:** the live-demo flow on one slide, with the backup screenshots;
   - **UI screenshots for slides 1 and 6:** the compare page for "Problem" and the UI in the architecture slide;
   - **the frontend items of Limitations and future work.**

6. **Defence prep: `docs/presentation/qa_frontend.md`.** 8–10 likely questions with short answers. For example:
   - How do you stream the answer?
   - How do you make sure citations can't point to nothing?
   - How did you test the UI?
   - Accessibility?
   - What happens when the backend is degraded?
   - Why mock-first?

## Acceptance criteria

- [ ] The demo script has been rehearsed at least once by the presenter, with the timing noted. Plan B has been tested (mock mode works offline).
- [ ] The backup video and the screenshots are in place.
- [ ] The docs and slide sections are written and consistent with the deployed version.
