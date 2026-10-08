# Frontend presentation: three minutes

## Before presenting

1. In `frontend/`, run `npm run dev` and open `http://127.0.0.1:5173`.
2. Keep mock mode selected unless the team has rehearsed the complete live stack.
3. Select RU. Use browser zoom appropriate for the projector.
4. Keep `frontend-home.png`, `frontend-results.png`, and `frontend-compare.png` from
   `docs/presentation/img/` available as backup slides. A backup video has not been recorded.

## 0:00–0:30: problem and scope

Explain that people ask questions in everyday language while legal texts use formal terminology.
Identify the visible demo banner: this frontend demonstration uses synthetic documents and
scripted answers, not real statutes or a measured trained model.

## 0:30–1:05: search

Click **Мне не платят зарплату**. Show the retrieved documents, article numbers, revision dates,
and status labels. Explain that the interface is wired to a typed REST API and can switch to
live mode when the backend and real corpus are ready.

## 1:05–1:50: answer and provenance

Click **Сформировать ответ**. Sources arrive first and answer text streams afterward.
Click **[1]** in the answer to open its article. Show the preserved paragraph numbering.
Click **Открыть на другом языке** to show the parallel Kazakh article. Press Escape to close.
Point out the disclaimer and explain why answers and source text have distinct visual treatments.

## 1:50–2:30: comparison

Open **Сравнение** and click the salary example again. Show the two columns.
Explain that demo ranking is a local illustration of the interaction: it is not evidence that
a semantic model outperforms a lexical baseline. Actual model quality belongs in the AI teammate's
evaluation with a labelled dataset.

## 2:30–3:00: contribution and boundaries

State the frontend contribution: responsive search UI, typed API integration, SSE streaming,
clickable provenance, bilingual article drawer, comparison, failure/cancellation states, tests.
The backend owns API and storage; the AI teammate owns corpus, models, and evaluation.
Describe what the team has actually integrated live, separately from this local demonstration.

## If asked about limitations

- Synthetic fixtures are not legal advice or current legislation.
- Kazakh UI translations require review by a Kazakh speaker.
- Admin and deployment were deferred for the same-day frontend MVP.
- Local automated checks do not establish real model quality or deployed latency.
- The latest backend handoff lists `/answer` as implemented with fake-ML tests; the frontend's live integration and real model output remain unverified.
