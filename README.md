# Adilet Search

Semantic search and source-cited answers over the legislation of the Republic of Kazakhstan, in Russian and Kazakh. Built as the AI module of **Legal Service** (Tehsnab Group, https://test.tehprof.kz/legal).

Course final project. Team: Daniil Talyzin, Yernur Kazhyakpar, Kuanysh Murat.

## What it does

- **Search in plain language.** Ask "мне не платят зарплату" and get the Labor Code articles about wage payment, not only articles that contain those words. Dense embeddings and keyword matching are combined, then a reranker reorders the top results.
- **Answers with citations.** An LLM writes a short answer from the retrieved articles only and cites them as `[1]`, `[2]`; every citation opens the article.
- **Official texts.** The corpus is the public AdiletCodex dataset (parsed from adilet.zan.kz): 8 codes, 9,259 articles, in both languages, stored verbatim.
- **Admin panel.** Usage statistics, the query log, system health, reindexing.
- **Keeps working when parts fail.** If the models or the vector index are down, search falls back to keyword search in the database.

## Final project (submission 23 November 2026)

- [Run guide for the final prototype](docs/tech/final_project.md) (`infra/start-final.ps1`: real models, production UI, Prometheus and Grafana on local ports) and the [readiness report](docs/report/final_readiness.md).
- [10-slide presentation](docs/presentation/final_deck.md) and [speaker guide](docs/presentation/final_speaker_guide.md).
- Research comparison of the pipeline with recent pretrained embedding models: [findings](docs/report/RESEARCH_FINDINGS.md), [executed notebook](ml/notebooks/Final_Research_Comparison.ipynb), [how to reproduce](docs/tech/research_benchmark.md).

Older bootstrap reports are superseded and must not supply final numbers.

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
| [docs/status/](docs/status/) | the current state of each part |
| [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | the original plan: scope, architecture, phases |
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

- The models are pretrained and not yet fine-tuned on legal text; quality numbers so far come from automatic (proxy) labels, not from human judgement. See [ml/MODEL_CARD.md](ml/MODEL_CARD.md).
- Only 8 codes are indexed by default.
- The system is a search aid, not legal advice.

How this repository was developed (three role briefs, shared rules, phase prompts) is described in [agents/README.md](agents/README.md) and [CLAUDE.md](CLAUDE.md).
