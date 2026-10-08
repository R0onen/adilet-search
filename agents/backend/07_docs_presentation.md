# BE-07: Technical documentation, integration guide, slides (week 6)

**Goal:** the platform is documented well enough that the customer's engineers could run it and integrate it, and the backend half of the defence is ready.

## Tasks

1. **`docs/tech/architecture.md`:**
   - the component diagram (Mermaid, consistent with PROJECT_PLAN §3);
   - **sequence diagrams** for `/search`, `/answer` (SSE), reindex with the alias switch, and degraded mode;
   - the deployment diagram (containers, networks, volumes, ports);
   - the data model (an ER diagram of the Postgres tables);
   - how the design meets each non-functional target (latency, scalability, fault tolerance, security).

2. **`docs/tech/api.md`:** how to use the API, with curl examples for every public endpoint and the admin flow, including how to consume SSE from JavaScript, Python and PHP. Link `contracts/openapi.json` and `/docs` (Swagger UI; decide whether it stays exposed in production and say so).

3. **`docs/tech/integration_guide.md`**, written for the Legal Service backend team:
   - server-to-server calls with `X-API-Key`;
   - the recommended timeouts and retries;
   - handling `degraded` and 429 responses;
   - mapping `article_id` back to their own document IDs (adilet `doc_id` is shared);
   - examples in PHP, Python and JavaScript;
   - embedding options (a link to our UI, an iframe, or the optional widget if Frontend built it);
   - data refresh: how a corpus update flows (new `corpus_version` → reindex).

4. **`docs/tech/infrastructure_sizing.md`.** Answers TOR §4.3 with **measured** numbers (from the load test and `docker stats`):
   - RAM/CPU per service;
   - throughput per vCPU;
   - when a GPU becomes worth it (the generator; reranking at higher QPS);
   - three configurations: the minimum (demo), a recommended production setup on CPU only, and production with a GPU for the LLM, each with rough monthly cost ranges;
   - scaling path: more backend replicas behind Caddy, Qdrant sharding/replication, a Postgres replica, a shared Redis cache.

5. **`docs/tech/operations.md`:** monitoring (dashboard panels and what they mean), the alert rules and how to respond to each, the log fields, backups. Link the runbook.

6. **Root `README.md`, developer section:** a quickstart in ≤ 5 commands (clone → `.env` → `docker compose --profile dev up -d` → index the sample → open the UI), plus links to each part's README.

7. **Presentation sections:** write `docs/presentation/sections/backend.md` (Marp) for these slides:
   - **6, System architecture:** one diagram plus the two flows in one line each;
   - **7, Deployment:** the topology, the URL, CI/CD, monitoring and backups;
   - **9, the backend half of Performance:** load-test p50/p95 at 10 and 25 users, the per-stage breakdown, the degraded drill result;
   - **10, the backend items of Limitations and future work.**

   Diagrams and screenshots go to `docs/presentation/img/`.

8. **Defence prep: `docs/presentation/qa_backend.md`,** with 12–15 likely questions and short answers. For example:
   - Why Qdrant?
   - How is 2 s guaranteed?
   - What happens if the ML service dies?
   - How do you reindex without downtime?
   - How is data protected?
   - How does it scale?
   - How does Legal Service integrate with it?
   - Why SSE and not WebSockets?

## Acceptance criteria

- [ ] Every doc listed above exists, is accurate for the deployed version, and has no TODOs left in it.
- [ ] A teammate who has not worked on the backend can follow the quickstart and the runbook from a clean clone. Ask the human to try it, and fix whatever they trip on.
- [ ] The slide sections and the Q&A are written. Every number can be traced to `load_test.md` or Grafana.
