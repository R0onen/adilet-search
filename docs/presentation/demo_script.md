# Live presentation: three minutes

> Updated baseline: the live stack now contains the complete extracted Labor and Environmental Codes in RU/KK (1,306 article-language records, 2,799 chunks). The original three-article run below is historical. Use `/data/processed/official-baseline` when restoring the current index. See [ingestion and difficult-question findings](qa_frontend.md) before presenting: source retrieval failed on several paraphrases, and generation produced substantive errors despite valid citation markers. Do not claim reliable arbitrary legal reasoning.

## Before presenting

Open http://127.0.0.1:5173 and confirm **Live API**. Select RU.
Generator: Groq `openai/gpt-oss-120b`, using a secret in ignored `.env.localtest`.
Corpus: official Adilet Labor Code snapshot downloaded 2026-10-08, articles 68, 88 and 113 in RU/KK. This is a three-article demonstration, not coverage of all legislation. Revision dates remain unknown rather than invented.
Search still uses bootstrap hash/BM25/lexical retrieval. The LLM generates from the retrieved official text; it is not a fine-tuned project model.

## Tested questions

| Question | Source | Expected source fact |
|---|---|---|
| Какова нормальная продолжительность рабочего времени в неделю? | 68 | Normal working time must not exceed 40 hours per week. |
| Какова продолжительность основного оплачиваемого ежегодного трудового отпуска? | 88 | 24 calendar days unless a longer period is provided by the Code, other legal acts, contracts or employer acts. |
| Какие сроки выплаты заработной платы? Что происходит, если день выплаты совпадает с выходным? | 113 | At least monthly, no later than the first ten days of the following month; contractual payday; payment before a coinciding weekend/holiday. |
| Жұмыс уақытының қалыпты ұзақтығы аптасына қанша сағат? | 68 KK | No more than 40 hours weekly. |

All four generated answers passed source-fact and citation checks. Six RU/KK retrieval questions ranked the expected article first. These smoke tests are not an evaluation benchmark; model output can vary.

Official sources: [RU](https://old.adilet.zan.kz/rus/docs/K1500000414), [KK](https://old.adilet.zan.kz/kaz/docs/K1500000414). Article anchors such as `#z88` were checked in downloaded HTML.

## Walkthrough

1. **0:00–0:30:** explain source retrieval plus cited generation; state the small corpus and external Groq model.
2. **0:30–1:00:** click **Сколько дней ежегодного отпуска?**. Show article 88 ranked first.
3. **1:00–2:00:** generate the answer; open citation [1]. Show the official paragraph, including the exceptions allowing longer leave. Switch to Kazakh and back. Open the official link if internet is available.
4. **2:00–2:30:** click **Когда должны выплачивать зарплату?** and generate an answer. Show article 113 and payment before a coinciding weekend/holiday.
5. **2:30–3:00:** explain React → FastAPI → PostgreSQL/Qdrant → ML service → Groq. Mention the disclaimer, citation checks and limited coverage. Comparison is an interaction demonstration, not proof that the bootstrap retriever beats a baseline.

Live example buttons submit the tested RU questions, or corresponding KK questions with KK UI. EN UI submits RU questions; no English statutory sources are indexed. Avoid the old ecology and dismissal examples, which are outside this corpus. Kazakh wording needs human review.

## Start and restore

From repository root in PowerShell:

```powershell
docker compose -p adilet-localtest --env-file .env.localtest --profile ml up -d --wait
```

From `frontend` in a separate terminal:

```powershell
$env:VITE_API_MODE='live'
$env:API_PROXY_TARGET='http://127.0.0.1:18000'
npm run dev
```

The generated corpus is preserved in ignored `data/processed/demo-official/`. Database volumes survive restarts. Restore this index with:

```powershell
docker compose -p adilet-localtest --env-file .env.localtest --profile ml exec -T backend python -m indexer --data-dir /data/processed/demo-official
```

Regenerate only when intentionally choosing a new official snapshot; rerun demo checks afterward:

```powershell
docker cp frontend/scripts/build-official-demo.py adilet-localtest-ml-service-1:/tmp/build-official-demo.py
docker compose -p adilet-localtest --env-file .env.localtest --profile ml exec -T ml-service python /tmp/build-official-demo.py
docker cp adilet-localtest-ml-service-1:/tmp/official-demo/. data/processed/demo-official
```

## Groq configuration

In ignored root `.env.localtest`:

```dotenv
ADILET_ML_GENERATOR_MODE=openai
LLM_BASE_URL=https://api.groq.com/openai
LLM_MODEL=openai/gpt-oss-120b
ANSWER_MAX_TOKENS=1024
```

Keep `LLM_API_KEY` secret, outside the frontend. The existing engine appends `/v1/chat/completions`; do not append `/v1` to this base URL. Recreate backend/ML with Compose after environment changes. No new SDK or dependency is needed. Questions and retrieved public text are sent to Groq.

[Free-tier limits](https://console.groq.com/docs/rate-limits) vary by account; a 429 means wait for quota reset. The free table currently lists this model at 30 requests/minute, 1,000/day, 8,000 tokens/minute and 200,000/day. Do not upgrade billing for this demo. If deliberately reverting to extractive `fallback`, disclose it.

## Evidence and backup

- Four real Groq answer checks passed with expected facts and valid source references; individual completion times were about 1.2–1.4 seconds, not a load benchmark.
- Live Edge browser passed generation, citation opening, official source link, KK switch and comparison; no page errors.
- Build/lint and 12 frontend unit tests passed.
- Local ignored evidence: `frontend/test-results/official-retrieval.json`, `groq-report.json`, `groq-live-answer.png`, `official-article.png`.
- Corpus includes extracted article JSON and raw-page SHA-256 provenance. Source wording is preserved with paragraph separation; amendment notes are separate. It is an educational snapshot, not a guarantee of current legal completeness.
- Record a backup video before presenting. Groq and official links need internet. Public HTTPS deployment remains separate work.
