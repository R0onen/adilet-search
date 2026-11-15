# Architecture

Adilet Search answers a question in Russian or Kazakh with the articles of Kazakhstan legislation that cover it, and can write a short answer that cites those articles.

## Components

```mermaid
flowchart LR
    U[Browser] -->|HTTPS| C[Caddy<br/>reverse proxy]
    C -->|/| F[Frontend<br/>static React app]
    C -->|/api| B[Backend<br/>FastAPI]
    C -->|/grafana| G[Grafana]
    B -->|SQL| P[(PostgreSQL<br/>articles, logs, feedback)]
    B -->|gRPC| Q[(Qdrant<br/>dense + sparse vectors)]
    B -->|HTTP| M[ML service<br/>embed, rerank, generate]
    M -->|OpenAI-compatible API| L[LLM]
    PR[Prometheus] -->|scrape /metrics| B
    PR --> M
    G --> PR
```

| Component | Role | Why this choice |
|---|---|---|
| Frontend | search page, streamed answer, article viewer, admin panel | a static build; no server-side state |
| Backend | the public API: orchestrates search, streams answers, logs queries, admin API | async FastAPI: the work is waiting on other services, so one process handles many requests |
| ML service | the models behind one small internal API | models can change (fine-tuned versions) without touching the backend; `contracts/ml_service.md` is the only link |
| Qdrant | vector index with dense and sparse vectors in one collection | hybrid search in one store; collection aliases give a switch without downtime |
| PostgreSQL | article texts, query logs, answers, feedback, index bookkeeping; full-text fallback | one relational store for everything that is not a vector |
| LLM | writes the answer from the retrieved articles | any OpenAI-compatible endpoint; the system works without it (search only) |

The interfaces are fixed in `contracts/`: `api.md` and `openapi.json` (public API), `ml_service.md` (backend ↔ ML), `data_schema.md` (corpus files).

## Search: `POST /api/v1/search`

```mermaid
sequenceDiagram
    participant U as Browser
    participant B as Backend
    participant M as ML service
    participant Q as Qdrant
    participant P as PostgreSQL
    U->>B: query, filters, mode
    B->>B: append legal terms for everyday words
    B->>M: /embed (query) → dense + sparse vector
    par dense
        B->>Q: nearest neighbours (top 50)
    and sparse
        B->>Q: BM25-weighted match (top 50)
    end
    B->>B: weighted reciprocal-rank fusion, collapse chunks to articles
    B->>M: /rerank (top 5 articles)
    B->>P: article and document rows
    B-->>U: ranked articles with snippets, timing, degraded[]
    B-)P: query log (after the response)
```

- **Query expansion.** People write "зарплата" or "вещдок"; the statutes say "заработная плата" and "вещественные доказательства". A dictionary of 34 such words (`backend/app/services/query_expansion.py`) appends the legal terms to the query that the models and the keyword search see. The user's words are never removed, and the logged and returned query is unchanged.
- **Hybrid retrieval.** The dense vector finds articles that mean the same as the question; the sparse (keyword) vector finds exact terms and article numbers. Reciprocal-rank fusion merges the two lists without tuning score scales.
- **Reranking.** A cross-encoder reads the question together with each of the top 5 articles and reorders them. It is the most expensive stage, so it has its own time budget.
- **Budgets.** Each stage has a timeout (`SEARCH_*_TIMEOUT_S`). The target is p95 ≤ 2 s for the whole request.

## Answer: `POST /api/v1/answer` (Server-Sent Events)

```mermaid
sequenceDiagram
    participant U as Browser
    participant B as Backend
    participant M as ML service
    participant L as LLM
    U->>B: question
    B->>B: search (as above), keep the top 5 articles
    B-->>U: event: sources
    B->>M: /generate (question + numbered sources)
    M->>L: chat completion, streamed
    loop tokens
        L-->>M: token
        M-->>B: token
        B-->>U: event: token
    end
    B->>B: check citations [n] against the sources
    B-->>U: event: done (final text, citations, grounded)
    B-)P: answer + query log
```

- The sources are sent **before** generation starts, so the user sees the law even if the LLM is slow or down.
- The model may only cite the numbered sources it was given. Citations to anything else are removed, and an answer without valid citations is marked as not grounded.
- SSE (not WebSockets) because the stream goes one way and plain HTTP passes every proxy.

## Reindex without downtime

```mermaid
sequenceDiagram
    participant A as Admin / CLI
    participant I as Indexer
    participant M as ML service
    participant Q as Qdrant
    A->>I: start (one job at a time)
    I->>I: validate the corpus files
    I->>Q: create collection legal_chunks__<version>
    loop batches
        I->>M: /embed (passages)
        I->>Q: upsert points
    end
    I->>Q: count points == chunks?
    I->>Q: move alias legal_chunks → new collection (atomic)
    Note over Q: the old collection is kept for rollback
```

Search always reads through the alias, so it serves the old index until the instant of the switch. A failed job deletes its own partial collection and changes nothing. Every index records the `index_compat_id` of the models that built it; the backend refuses an index built with other models.

## Degraded modes

```mermaid
flowchart TD
    S[search request] --> E{embed + vector search OK?}
    E -- yes --> R{rerank within budget?}
    E -- "no: ML service or Qdrant down,<br/>circuit open, index incompatible" --> FTS[PostgreSQL full-text search<br/>degraded: semantic]
    R -- yes --> OK[full result]
    R -- no --> FU[fused order<br/>degraded: rerank]
    FTS --> X{PostgreSQL OK?}
    X -- no --> E503[503]
```

A circuit breaker per dependency stops calls after 5 consecutive failures and probes again after 20 s, so a dead service costs no timeouts. If the LLM fails, the answer stream ends with an `error` event after the sources.

## Data model (PostgreSQL)

```mermaid
erDiagram
    documents ||--o{ articles : contains
    query_logs ||--o| answers : "may have"
    query_logs ||--o{ feedback : receives
    index_jobs ||--o| index_state : builds
    documents { text doc_id PK "adilet code" text lang PK text title text status date revision_date }
    articles { text article_id PK "doc:lang:unit" text text tsvector tsv "full-text fallback" text parallel_article_id "other language" }
    query_logs { uuid query_id PK text query text session_hash "salted, anonymous" jsonb results jsonb timing_ms text_array degraded }
    answers { uuid answer_id PK uuid query_id FK text text smallint_array citations bool grounded int ttft_ms }
    feedback { bigint id PK uuid query_id FK text target smallint rating }
    index_jobs { uuid job_id PK text status float progress }
    index_state { text collection PK text index_compat_id int points_count }
    admin_users { int id PK text username text password_hash "bcrypt" }
```

Vectors live only in Qdrant; each point's payload carries the chunk text and the filter fields (language, document, status, date).

## How the design meets the targets

| Target | How |
|---|---|
| Response time ≤ 2 s | per-stage budgets; the reranker is capped (top 5, 256 tokens) and skipped when slow; query embeddings and responses are cached; measured in `docs/report/load_test.md` |
| Fault tolerance | full-text fallback, circuit breakers, sources before generation, health checks and automatic container restarts |
| Updating the index | versioned collections behind an alias; the old index serves until the new one is complete; rollback is an alias move |
| Scalability | the backend is stateless apart from a per-process cache and rate limiter, so replicas can be added behind the proxy once those move to a shared store; Qdrant and PostgreSQL scale independently |
| Security | `docs/tech/security.md` |
| Observability | request ids in every log line and response; Prometheus metrics per search stage; Grafana dashboard and alert rules |
| Logging and analytics | every query, answer and rating is stored; the admin panel reads them |

## Deployment view

`docker-compose.prod.yml` runs all of the above on one host. Only Caddy publishes ports (80 and 443); the other containers talk on the internal Docker network. Named volumes hold the database, the index, the model cache, the metrics and the certificates. See `docs/tech/deployment.md` and `docs/tech/runbook.md`.
