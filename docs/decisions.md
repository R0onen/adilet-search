# Decision log

Append-only. Record a decision whenever you choose between real alternatives. These entries are the raw material for the "model selection rationale" sections of the reports and for questions at the defence.

Format:

```
## D-NNN: Title
- Date · Status (proposed / accepted / superseded by D-xxx) · Owner
- Decision:
- Why (evidence, constraints):
- Alternatives considered and why not (for now):
- Revisit if:
```

---

## D-001: Monorepo with per-agent directory ownership
- 2026-10-05 · accepted · all
- **Decision:** one repository; `ml/`, `backend/` and `frontend/` are each owned by one agent; interfaces live in `contracts/`.
- **Why:** three agents work in parallel. Clear ownership prevents them overwriting each other, and one repo keeps contracts, CI and docs in one place.
- **Alternatives:** three repos (harder to keep contracts in sync); a shared free-for-all repo (agents trample each other).
- **Revisit if:** the team wants to hand the backend over to the customer separately.

## D-002: Contract-first interfaces, with generated types
- 2026-10-05 · accepted · Backend, Frontend
- **Decision:** `contracts/api.md` is written first. `openapi.json` is generated from FastAPI, and the frontend generates its TS types from `openapi.json`. CI fails on drift.
- **Why:** the frontend can build against mocks from day 1, and a mismatch becomes a compile error instead of a demo-day bug.
- **Revisit if:** never during this project.

## D-003: Separate internal `ml-service` instead of importing ML code into the backend
- 2026-10-05 · accepted · ML, Backend
- **Decision:** models run in their own FastAPI service with `/embed`, `/rerank` and `/generate`. The backend talks to it over HTTP.
- **Why:** it keeps heavy ML dependencies out of the API image, the ML agent owns inference end to end (final-assignment task 1), models can be versioned and scaled independently, and the backend can be developed against a fake.
- **Alternatives:** an in-process Python package (coupled releases, huge backend image); HF text-embeddings-inference (less control over sparse encoding and prompts).
- **Revisit if:** the HTTP overhead shows up in the latency budget (unlikely: a few ms).

## D-004: Qdrant for vectors, PostgreSQL for everything else
- 2026-10-05 · accepted · Backend
- **Decision:** Qdrant holds dense + sparse vectors with payload filters, behind a collection alias. Postgres holds documents, articles, logs, feedback, admin users and the full-text fallback.
- **Why:** Qdrant does dense and BM25-style sparse search in one place, filters on metadata, and the alias switch gives zero-downtime reindexing and instant rollback. Postgres is what the customer most likely already runs.
- **Alternatives:** pgvector only (no native BM25, weaker ANN at scale); Elasticsearch/OpenSearch (heavier to run on one small VM).

## D-005: Fusion on the client side, with the formula fixed in the contract
- 2026-10-05 · accepted · ML, Backend
- **Decision:** the backend runs the dense and sparse searches separately and fuses them with weighted RRF exactly as specified in `contracts/ml_service.md` §2, tested against `contracts/fixtures/fusion_cases.json`.
- **Why:** offline experiments and production then compute the same ranking, so offline metrics transfer to the deployed system.

## D-006: Article-level chunking with a contextual header
- 2026-10-05 · accepted · ML
- **Decision:** the retrieval unit is an article (split if it exceeds ~400 tokens). The embedded text starts with "Act. Article N. Title".
- **Why:** users need the exact provision, not the whole law. The header carries context that the article body often lacks.
- **Revisit if:** the error analysis shows split articles losing relevance.

## D-007: The 2 s SLA applies to `/search`; `/answer` is streamed
- 2026-10-05 · accepted · all
- **Decision:** `/search` must meet p95 ≤ 2 s on CPU. `/answer` streams sources first, then tokens, and we report TTFT.
- **Why:** LLM generation cannot finish in 2 s on CPU hardware. Search is the TOR's core function; the answer is the extension.

## D-008: The LLM sits behind an OpenAI-compatible endpoint
- 2026-10-05 · accepted · ML
- **Decision:** `ml-service` calls the LLM through an OpenAI-compatible API. That can be llama.cpp with a GGUF (CPU), vLLM with the LoRA adapter (GPU), or a hosted endpoint, chosen by env vars.
- **Why:** the generator backend can change with hardware and budget without code changes.

## D-009: Language codes `ru` / `kk`
- 2026-10-05 · accepted · all
- **Decision:** use ISO 639-1 codes everywhere: `kk` for Kazakh, not `kz` (which is the country code).

## D-010: Assignment 4 is framed as query–article relevance classification (the reranking stage)
- 2026-10-05 · accepted · ML
- **Decision:** A4's "features → target" task is binary relevance of (query, candidate article) pairs drawn from the fixed first-stage top-50. Its configurations are TF-IDF + LogReg → embeddings + LogReg/LightGBM → zero-shot cross-encoder → fine-tuned cross-encoder.
- **Why:** it fits the A4 structure exactly and its winner becomes the production reranker, so the assignment work is not throwaway.

## D-011: Training on Colab/Kaggle; artifacts on the Hugging Face Hub
- 2026-10-05 · accepted · ML
- **Decision:** GPU training runs on free Colab/Kaggle GPUs. Datasets, checkpoints, adapters and GGUF files go to private HF repos, pinned by revision in the manifest.
- **Why:** no GPU budget, and the artifacts must be reachable from laptops, notebooks and the server.

## D-012: No customer support: own data pipeline and own hosting
- 2026-10-08 · accepted · all (recorded by Backend)
- **Decision:** Tehsnab Group provides neither a database export nor a test VM. ML builds the corpus with its own polite scraper of adilet.zan.kz (PROJECT_PLAN §6 fallback). Backend deploys to a VPS and domain that the team rents (PROJECT_PLAN §9 fallback).
- **Why:** the team confirmed there is no customer support for this project.
- **Consequences:** BE-06 needs a human to rent a VPS (Ubuntu 24.04, ≥ 4 vCPU / 16 GB RAM / 80 GB SSD) and a domain (or a free dynamic-DNS name) in week 5. The integration guide describes integration with Legal Service as a proposal, not something tested against their system.
- **Revisit if:** the customer later offers an export or a VM.

## D-013: `/health` status ignores the LLM; enums are TEXT + CHECK
- 2026-10-08 · accepted · Backend
- **Decision:** (1) `/health` is `down` only when Postgres is down (not even the full-text fallback can run), `degraded` when Qdrant or the ML search models fail, and `ok` otherwise. The LLM is reported but does not change the status. (2) Enumerated columns are `TEXT` with `CHECK` constraints instead of Postgres enum types. At most one active index job is enforced by a partial unique index.
- **Why:** (1) the 2 s search SLA is the core function, and the answer feature degrades separately (`degraded: ["generation"]`); this also matches the contract example. (2) Adding a value becomes a one-line migration (Postgres enums cannot drop values), and the single-job rule holds even with several backend workers.
- **Alternatives:** count the LLM in `status` (the dashboard would show "degraded" every time the CPU LLM is off); application-level locking for jobs (racy with several workers).
