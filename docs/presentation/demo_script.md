# Adilet Search: presentation and local demo guide

## Where to open it

- App: http://127.0.0.1:5173
- API documentation: http://127.0.0.1:18000/api/v1/docs
- Health: http://127.0.0.1:18000/api/v1/health

The app is deployed locally on this laptop. These addresses are not a public website and will not open the app on the professor's own laptop. Keep Docker Desktop and the frontend process running. Search uses local services; generated answers require internet access to Groq.

## Your opening explanation (about 30 seconds)

“Our project is Adilet Search, a prototype for finding and understanding Kazakhstan legislation. A user asks a question in Russian or Kazakh. The app retrieves relevant articles and asks an AI model to explain them using those sources. The user can open the original article and check the answer. We built it as a group of three, covering backend, frontend and AI. My part is the frontend.”

## How it works, in plain language

This approach is called **RAG: retrieval-augmented generation**. First we find documents; then we give selected source text and the user's question to the language model. The answer therefore has specific evidence the user can inspect.

The flow is:

**Question → search index → ranked articles → Groq language model → streamed answer → source inspection.**

- **React/TypeScript frontend:** search form, filters, results, answer display, article drawer and language switching.
- **FastAPI backend:** validates requests, runs search and streams answers to the browser.
- **PostgreSQL:** stores documents, articles and application records.
- **Qdrant:** stores indexed passages for retrieval.
- **ML service:** creates retrieval vectors, ranks candidates and calls Groq's hosted `openai/gpt-oss-120b` model.

The current search is a bootstrap implementation using hash vectors and lexical ranking. Hash vectors are not trained semantic embeddings. The LLM generates real answers, but it cannot reliably compensate for missing or irrelevant retrieved sources.

## What data we use

We downloaded official Adilet pages for the Labor and Environmental Codes in RU and KK. HTML is cached, parsed into articles, split into smaller searchable passages and indexed. We preserve source wording and links, with amendment notes stored separately.

There are **653 article IDs in two languages: 1,306 article-language records and 2,799 chunks**. Eighteen removed article records are marked excluded. This is a snapshot, not all Kazakhstan legislation; revision dates and amendment effective dates are not fully verified. These documents are a retrieval corpus, not data used to train our own LLM.

## Live demonstration (about 4 minutes)

| Step | What to do | What to explain |
|---|---|---|
| 1. Search | Open the app, confirm **Live API**, select RU. Click **Сколько дней ежегодного отпуска?** | The frontend calls the real backend. Show article 88 ranked first. |
| 2. Filters | Point out source-language, document and in-force filters. | Users can narrow the evidence. UI language and source language are separate. |
| 3. Answer | Click **Сформировать ответ**. | Sources are supplied to the model; answer text arrives progressively instead of waiting for a complete response. |
| 4. Verify | Open the first source button below the answer. | Article 88 gives 24 calendar days, with provisions allowing longer leave. The article is the evidence; the answer is an AI explanation. |
| 5. Languages | In the drawer, click **Открыть на другом языке**; then Escape. | Parallel RU/KK source articles are linked. The interface also supports English, but English law sources are not indexed. |
| 6. Compare | Open **Сравнение** and click the working-week example. | Show keyword and hybrid results side by side. This illustrates the two modes; it does not prove semantic superiority. |

If time remains, ask: **Какие сроки выплаты заработной платы? Что происходит, если день выплаты совпадает с выходным?** Article 113 should rank first. Another tested question is **Жұмыс уақытының қалыпты ұзақтығы аптасына қанша сағат?**, which should retrieve article 68 KK.

Inline `[1]` references are clickable when the model follows the expected format. Sometimes it emits a different notation; use the separate source buttons. Do not describe a warning or malformed citation as successful evidence verification.

## Your frontend contribution

“I implemented the search interface, filters, result cards, streamed answer panel, source links, article drawer, RU/KK article switching and comparison page. I integrated the typed backend API and handled loading, errors and cancelled generation. The frontend has responsive layouts, RU/KK/EN interface text and automated checks.”

You can mention that 12 unit tests, build and lint passed in earlier validation. Today's browser rehearsal passed live answer display, source-button opening, the official article, KK switching and comparison. The strict inline-citation check failed on one model response; source buttons still worked.

## Likely professor questions

**Did you train the model?** No. This MVP uses a pretrained hosted model. Our work is data ingestion, retrieval, application integration and source-based presentation of answers.

**How accurate is it?** We ran a small diagnostic set, not a formal accuracy benchmark. All expected sources appeared in the top five for 8 of 13 supported questions. Paraphrases and multi-part questions exposed retrieval failures and some incorrect generated claims. A valid citation number does not establish correctness.

**Does it learn from users?** No automatic training or adaptation is implemented. Answers change with the question and retrieved context.

**What would you improve?** Real multilingual semantic embeddings, better ranking and query decomposition, stricter evidence checks, reliable citation formatting, verified legal dates and a larger human-reviewed evaluation set. Admin UI and public hosting are not part of this demonstrated frontend.

**Why is this useful?** It brings search, explanation and source verification into one flow. It helps users inspect relevant legislation, while keeping the original article accessible.

## If something fails

If Groq is unavailable or rate-limited, show search, article viewing, language switching and comparison. Explain the external generator dependency. A screenshot from a successful rehearsal is in `frontend/test-results/groq-live-answer.png`; label it as a recorded result. Do not silently present mock answers as live AI.

To restart services from the repository root:

```powershell
docker compose -p adilet-localtest --env-file .env.localtest --profile ml up -d --wait
```

In another PowerShell terminal, from `frontend`:

```powershell
$env:VITE_API_MODE='live'
$env:API_PROXY_TARGET='http://127.0.0.1:18000'
npm run dev
```

Database volumes persist; restarting does not normally require indexing again. If restoring the current corpus is necessary, use `/data/processed/official-baseline`, not the old three-article dataset. Full ingestion commands and failure evidence are in [qa_frontend.md](qa_frontend.md).
