# FE-02: Search experience (week 2)

**Goal: G1.** A user types a plain question in RU or KK and gets a clean, trustworthy result list. It works on mocks and against the live dev API once Backend's BE-02 lands.

## Tasks

1. **Home / search page.**
   - A large search box: autofocused, submits on Enter, with a counter for the 500-char limit and a validation message.
   - Example query chips: the three TOR examples plus one KK example (agree on the KK one with a Kazakh speaker).
   - The detected language is shown after a search ("Язык запроса: русский").
   - A mode control under "Расширенный поиск": Smart (hybrid, the default), Semantic, Keyword.

2. **Filters** (a sidebar on desktop, a drawer on mobile):
   - document types (multi-select);
   - specific acts (a searchable multi-select fed by `GET /documents?lang=`);
   - "Только действующие" (on by default);
   - an adoption date range;
   - a reset button.

3. **URL state.** The query lives in the URL, e.g. `/search?q=…&lang=auto&mode=hybrid&types=code&docs=K1500000414&in_force=1&from=&to=`. Searches are shareable, back/forward works, and a reload restores the search.

4. **Result card:**
   - the article number and title (a link to `/article/:id?q=`);
   - the act short title;
   - badges: doc type, status, language, "ред. от {revision_date}";
   - the snippet with `highlights` rendered as `<mark>`.

   Actions:
   - open the article;
   - open on adilet ↗ (a new tab, `rel="noopener"`);
   - **copy citation** (e.g. «Трудовой кодекс РК, ст. 113»);
   - 👍 / 👎 feedback (wired in FE-03).

5. **Result list:**
   - a summary line: «Найдено 10 норм за 0,42 с»;
   - the pipeline version in small muted text;
   - a `degraded` banner (contract values → friendly text, e.g. «Интеллектуальный поиск временно недоступен — показаны результаты полнотекстового поиска»).

6. **States:**
   - a loading skeleton;
   - empty (suggestions: rephrase, remove filters, switch to Smart mode);
   - an error with retry;
   - a validation error;
   - 429 with a countdown taken from `Retry-After`.

7. **Data fetching:** TanStack Query, keyed by the full request. A new search cancels the in-flight one; the previous results are cached for back navigation.

8. **Tests:**
   - component tests for the result card (badges, highlights, the copy-citation text);
   - filters ↔ URL sync;
   - the empty/error/degraded states;
   - a Playwright e2e test on mocks: type a query → results → open an article.

## Acceptance criteria (G1)

- [ ] On mocks, every state can be reached and looks right on mobile (360 px) and desktop.
- [ ] Against the live dev API (`VITE_API_MODE=live`, Backend's stack up), the three TOR queries return results. Until ML ships `data/sample/`, Backend's synthetic corpus is acceptable. Start it with `docker compose --profile dev up -d --build`, then index it with `docker compose exec backend sh -c "python -m dev.sample_corpus /tmp/sample && python -m indexer --data-dir /tmp/sample"`. Re-check with real Labor Code results once ML's sample is indexed. Put a screenshot in the status file.
- [ ] `timing_ms` keys are optional (e.g. no `rerank` in `keyword` mode); the summary line handles missing stages.
- [ ] Any contract mismatches found are reported to Backend through the status file.
