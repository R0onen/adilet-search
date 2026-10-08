# FE-03: AI answer panel, article viewer, feedback (week 3)

**Goal: G2.** The answer streams in above the results. Each `[n]` is a clickable citation that leads to the exact article. Users can read the whole article and rate results and answers.

## Tasks

1. **The answer panel** (`features/answer/`).
   - **When it starts:** automatically, in parallel with `/search`, when the setting «Показывать AI-ответ» is on (the default; persisted). It has a Stop button and a Regenerate button.
   - **Stream handling** via `sse.ts`:
     - `sources`: show a compact source list right away (ref number, act + article, link);
     - `token`: append text progressively. The panel keeps a stable height so the page doesn't jump;
     - `done`: **replace** the text with `done.text` (it is authoritative) and show the timing in small text. `finish_reason: "no_results"` means search found nothing and no LLM ran; show the not-found state, not an error;
     - `error` (`generation_unavailable`, sent after `sources`): show "the answer is temporarily unavailable" and keep the sources and search results usable. Drill it with `FAKE_ML_FAIL=generate docker compose --profile dev up -d fake-ml`;
   - **Abort** on a new query, on navigation and on unmount.
   - **Progress copy:** «Ищем нормы…» until `sources`, then «Формируем ответ…» until the first token.
   - **Rendering:** a markdown subset (paragraphs, lists, bold), sanitised. Each `[n]` becomes a citation chip:
     - hovering or focusing it shows a preview (act, article, snippet);
     - clicking it opens `/article/:id?q=…`;
     - it is keyboard accessible and has an aria-label like «Источник 1: Трудовой кодекс РК, статья 113».
   - **When `grounded: false`:** a neutral style with the text «В найденных нормах нет прямого ответа» and a nudge to read the results.
   - **The panel always shows** the «AI-ответ» label, the disclaimer, and «Сформировано на основе N статей».
   - **Copy answer** produces plain text with the citations expanded into a list of sources at the end.

2. **The article page** (`/article/:articleId`):
   - breadcrumbs: act → section → chapter → article;
   - the title, badges (status, "excluded" when it applies, revision date, language) and the act's metadata;
   - the full text **verbatim**: `white-space: pre-line`, with numbered points intact;
   - query terms highlighted when the page is opened with `?q=`, plus "next match" navigation;
   - amendment notes in a collapsible «История изменений» section;
   - prev/next article navigation, and a RU ↔ KK switch through `parallel_article_id` (disabled with a tooltip when there is none);
   - "open on adilet" and "copy citation" actions;
   - "back to results" restores the previous search state and scroll position;
   - 404 and loading states.

3. **Feedback** (`POST /feedback`):
   - 👍/👎 on each result card and on the answer;
   - an optional comment box after 👎 («Что не так?»);
   - an optimistic UI with one active vote per item per session (stored in sessionStorage); errors fail quietly with a toast.

4. **Tests:**
   - the citation parser and renderer (`[1]`, `[1][3]`, a ref not in the sources is rendered as plain text);
   - the stream lifecycle with MSW (sources → tokens → done replaces the text);
   - the error path; abort when a new query starts;
   - the article page (verbatim rendering, the parallel switch, prev/next);
   - feedback (optimistic UI, rollback on error);
   - e2e: query → answer → click citation [1] → the article page opens with highlights.

## Acceptance criteria (G2)

- [ ] Against the live dev stack with ML v0, all three TOR queries stream an answer, and every citation opens the right article.
- [ ] A slow stream does not cause layout shifts. Stop, Regenerate and a new query all cancel cleanly (check the Network tab).
- [ ] Every UI string is in the i18n files. The KK strings that still need review are listed in the status file.
