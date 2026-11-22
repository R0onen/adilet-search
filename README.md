# Adilet Search

Semantic search and source-cited answers over the legislation of the Republic of Kazakhstan, in Russian and Kazakh. Built as the AI module of **Legal Service** (Tehsnab Group, https://test.tehprof.kz/legal).

**Live demo:** https://bacterium-margarita-coveted.ngrok-free.dev (on the first visit ngrok shows a warning page: click *Visit Site*).

Course final project. Team: Daniil Talyzin, Yernur Kazhyakpar, Kuanysh Murat.

## What it does

- **Search in plain language.** Ask "работодатель задерживает зарплату" and get the Labor Code article on the terms of wage payment, not only articles that contain those words. Everyday words are expanded into legal terms, dense embeddings and keyword matching are combined, then a reranker fine-tuned on legal questions reorders the top results.
- **Answers with citations.** An LLM writes a short answer from the retrieved articles only and cites them as `[1]`, `[2]`; every citation opens the article. When the articles do not answer the question directly, it says so and reports what they do say.
- **Official texts.** The corpus is the public AdiletCodex dataset (parsed from adilet.zan.kz): 40 acts (23 codes and 17 laws), 20,490 articles in Russian and Kazakh, stored verbatim. A smaller 8-code corpus is used for training and experiments.
- **Admin panel.** Usage statistics, the query log, system health, reindexing.
- **Keeps working when parts fail.** If the models or the vector index are down, search falls back to keyword search in the database.

## Results

| What | Result |
|---|---|
| Right article first, 195 test questions (live API, 40 acts) | 82.6% (nDCG@10 0.871) |
| Everyday questions about the added acts, right article in the top 10 | 87% (keyword search alone: 64%) |
| Generated answers citing the right article when it was retrieved | 35 of 35 |
| 10 concurrent users, cache off | p95 1.2 s |

Details: [model card](ml/MODEL_CARD.md), [final evaluation](docs/report/final_eval.md), [load test](docs/report/load_test.md).

## Documentation

- [Architecture](docs/tech/architecture.md), [deployment](docs/tech/deployment.md), [runbook](docs/tech/runbook.md), [security](docs/tech/security.md).
- [Run the full system](docs/tech/deployment.md) on a server or locally ("Local check"), and the [requirement coverage](docs/report/final_readiness.md).
- Model training: [Assignment 3](docs/report/A3_report.md) and [Assignment 4](docs/report/A4_report.md) reports, with executed notebooks in `ml/notebooks/`.
- Comparison with recent pretrained embedding models: [findings](docs/report/RESEARCH_FINDINGS.md), [how to reproduce](docs/tech/research_benchmark.md).
- [Presentation](docs/presentation/final_deck.pdf) and [speaker guide](docs/presentation/final_speaker_guide.md).

## Quick start (fake models, no downloads)

Needs Docker Desktop and Git. From the repository root:

```bash
cp .env.example .env
```

```bash
docker compose --profile dev up -d --build
```

```bash
docker compose exec backend sh -c "python -m dev.sample_corpus /tmp/sample && python -m indexer --data-dir /tmp/sample"
```

```bash
cd frontend && npm ci && VITE_API_MODE=live npm run dev
```

Open `http://127.0.0.1:5173`. This stack uses a stand-in for the models and an invented test corpus: it shows that everything is wired together, not search quality. In PowerShell, set the variable first: `$env:VITE_API_MODE = "live"; npm run dev`.

## The real thing (real models, real laws)

See [backend/README.md](backend/README.md) → "Run the whole project". In short: build the corpus, start the stack with the `ml` profile (the models download once, about 1.6 GB), index the corpus (about 45 minutes on a laptop CPU), and add an LLM key for generated answers.

## Where things are

| Path | What |
|---|---|
| [backend/](backend/README.md) | the public API (FastAPI), the indexer, tests, the load test |
| [ml/](ml/README.md) | the corpus importer, the ML service (embedder, reranker, generator), evaluation, notebooks |
| [frontend/](frontend/README.md) | the web UI and the admin panel (React) |
| [contracts/](contracts/) | the interfaces between the parts: public API, ML service, data schema, changelog |
| [infra/](infra/) | reverse proxy, Prometheus, Grafana |
| [docs/tech/](docs/tech/) | architecture, deployment, runbook, security, integration guide |
| [docs/report/](docs/report/) | evaluation, load test, assignment reports |
| [docs/presentation/](docs/presentation/) | slides, speaker guide, demo script |
| `docker-compose.yml`, `docker-compose.final.yml`, `docker-compose.prod.yml` | the development stack, the final-prototype overlay (local ports) and the public stack behind a reverse proxy |

## Checks

```bash
cd backend && uv run pytest && uv run ruff check . && uv run mypy app dev indexer
```

```bash
cd ml && uv run --extra dev pytest
```

```bash
cd frontend && npm run lint && npm test && npm run build
```

CI runs these on every pull request, plus integration tests on real PostgreSQL and Qdrant and a full-stack smoke test in Docker.

## Limits

- Quality numbers come from LLM-written test questions with automatic labels; a person checked 60 of them. There is no gold set written by lawyers. See [ml/MODEL_CARD.md](ml/MODEL_CARD.md).
- Kazakh questions are answered less well than Russian ones.
- The corpus is a snapshot of 17 September 2026 and covers 40 acts; later amendments and other acts are not in it.
- The system is a search aid, not legal advice.
