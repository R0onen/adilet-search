# Load test of `/search`

**Result on the deployed configuration (15 November 2026).** Pipeline 1.0.0 on the 40-act index, 10 concurrent users, cache off: p95 **1.2 s**, 981 hybrid searches, none failed, 1 answered without reranking. Details in the last section.

**Result on the 8-code index (12 November 2026).** With the reranker limited to the first 5 fused articles at 256 tokens, `/search` meets the target of p95 ≤ 2 s at 10 concurrent users on the full corpus: p95 **0.88 s** with the cache switched off, no failed and no degraded responses. At 25 users without a cache the reranker is saturated and most responses fall back to the fused order. The original setting (20 articles, 384 tokens) did not hold 10 users.

All numbers were produced by `backend/loadtests/locustfile.py`. The sections up to "Limits" describe the runs of 12 November 2026.

## Setup

| | |
|---|---|
| Hardware | laptop, Intel Core i7-13700HX (16 cores, 24 threads), Windows 11; Docker Desktop (WSL2) with 24 CPUs and 7.6 GiB of RAM for all containers |
| Stack | `docker compose --profile ml`: backend (1 process), ML service on CPU, Qdrant, PostgreSQL |
| Models | pipeline `0.2.0`: `intfloat/multilingual-e5-base`, `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |
| Index | full corpus: 16,264 chunks of 9,259 articles (8 codes, RU and KK) |
| Load | 10 or 25 simulated users, each waiting 1–3 s between requests, 5 minutes per run |
| Mix | 90% hybrid search, 10% keyword search; generated answers off (the hosted LLM has a daily token limit) |
| Questions | 803 LLM-written questions of `data/eval/synthetic/`, drawn at random |
| Failure rule | any non-200 response **and** any `degraded` response counts as failed |
| ML service code | commit `b545178` (model calls in one worker thread pool, PyTorch default threads) |

The rate limits stayed on; every request carried a new session id, as many separate visitors would.

## Runs (hybrid search)

| # | Reranker | Cache | Users | Requests | Failed or degraded | p50 | p95 | p99 | Requests/s |
|---|---|---|---|---|---|---|---|---|---|
| 1 | top 20, 384 tokens | on | 10 | 1,184 | 1,153 (97%) | 85 ms | 1,600 ms | 2,100 ms | 4.0 |
| 2 | top 5, 256 tokens | on | 10 | 1,199 | 0 | 280 ms | 670 ms | 1,000 ms | 4.0 |
| 3 | top 5, 256 tokens | on | 25 | 3,116 | 0 | 8 ms | 630 ms | 1,100 ms | 10.4 |
| 4 | top 5, 256 tokens | **off** | 10 | 1,055 | **0** | 520 ms | **880 ms** | 1,100 ms | 3.5 |
| 5 | top 5, 256 tokens | **off** | 25 | 2,693 | 2,490 (92%) | 130 ms | 2,600 ms | 2,900 ms | 9.0 |

Keyword search (PostgreSQL full-text, no models) stayed under 200 ms at p95 in every run.

How to read the runs:

- **Run 1** is the starting point. One rerank of 20 articles took 1.0–1.4 s for a single user, so at 4 requests per second the calls queued, passed the 1.5 s budget, and the circuit breaker switched the reranker off. The low median is the fused order returned without reranking.
- **Runs 2 and 3** look better than they are: there are only 803 distinct questions, so about two thirds of the requests in run 3 were served from the response cache (5-minute TTL). They show what repeated questions cost, not the capacity of the models.
- **Run 4 is the acceptance run**: every request goes through embedding, retrieval and reranking.
- **Run 5** shows the limit. The models can serve about 4 uncached searches per second on this machine; 25 users ask for about 10.

### Where the time goes (run 4, mean per request, from the Prometheus stage metrics)

| Stage | Mean |
|---|---|
| embed the query | 111 ms |
| dense + sparse retrieval | 19 ms |
| fusion | < 1 ms |
| rerank 5 articles | 385 ms |
| whole request | 483 ms |

The reranker is 80% of the request. Quantizing it to int8 in PyTorch did not help (785 ms against 867 ms for 20 articles at 256 tokens), so the number of candidates and their length are the levers that work on CPU.

## What the smaller reranker costs in quality

Same live API, hybrid mode, the 195 **test** questions of the synthetic set (labels are automatic: the article the question was written from is the only relevant one), rerank budget raised so that nothing is skipped:

| Reranker | Right article first | MRR@10 | nDCG@10 | Recall@10 | Sequential latency p50 |
|---|---|---|---|---|---|
| off (fused order) | 72.8% | 0.805 | 0.839 | 0.944 | 67 ms |
| top 5, 256 tokens | 83.1% | 0.867 | 0.885 | 0.944 | 288 ms |
| top 10, 256 tokens | 83.6% | 0.879 | 0.895 | 0.944 | 480 ms |
| top 20, 384 tokens | 85.6% | 0.898 | 0.913 | 0.959 | 1,379 ms |

Going from 20 to 5 candidates loses 2.5 points of "right article first" and keeps 10 of the 13 points the reranker adds, for a fifth of the time. The manifest now sets `rerank_top_n: 5` and `max_seq_len: 256`.

## Limits of this test

- One machine, a laptop with more cores than the planned 4 vCPU server; on 4 vCPU the reranker will be slower and the capacity lower. Repeat run 4 on the real server before quoting it for that server.
- Generated answers were not load-tested.
- The runs of 12 November were made before the bounded inference pool (`ADILET_ML_INFERENCE_WORKERS`, `ADILET_ML_CPU_THREADS`) was merged. The run of 15 November below is on the merged code.
- The earlier sample-corpus measurements in `final_load*.json` use another harness, 20 or 3 rerank candidates and 100 requests; they are not comparable with this table.

## Acceptance run on the deployed configuration (15 November 2026)

| | |
|---|---|
| Stack | `docker-compose.prod.yml`: requests go through the Caddy reverse proxy, as on the server |
| Models | pipeline `1.0.0`: `intfloat/multilingual-e5-base`, the fine-tuned reranker, 5 candidates at 256 tokens |
| ML service | 2 inference workers, 4 CPU threads each |
| Index | 40 acts: 41,074 chunks of 20,490 articles (RU and KK) |
| Search | with query expansion (everyday words → legal terms) |
| Load | 10 users, 1–3 s between requests, 5 minutes, cache off (`CACHE_TTL_S=0`), same questions and failure rule as above |

| Requests | Failed | Degraded | p50 | p95 | p99 | Requests/s |
|---|---|---|---|---|---|---|
| 981 hybrid | 0 | 1 (reranker timeout, answered in fused order) | 650 ms | **1,200 ms** | 1,800 ms | 3.3 |
| 137 keyword | 0 | 0 | 110 ms | 460 ms | 540 ms | 0.5 |

The target (p95 ≤ 2 s at 10 users) is met. Compared with run 4, the median is 130 ms higher: the index is 2.5 times larger, the ML service runs two inference workers of 4 threads instead of one pool with PyTorch's default thread count, and requests pass through the proxy. One search in 981 exceeded the 1.5 s reranker budget and was returned in fused order, marked `degraded`.

Raw output: `backend/loadtests/out/t2_users10*` (not committed).

## Next steps if more capacity is needed

1. An ONNX int8 build of the reranker (published for this model) is the usual 2–3× on CPU.
2. A GPU for the ML service (`docker-compose.gpu.yml`).
3. A shared cache and more backend processes do not help until the reranker is faster.

## Reproduce

```bash
cd backend && uv run locust -f loadtests/locustfile.py --host http://localhost:8080 --headless --users 10 --spawn-rate 5 --run-time 5m --csv loadtests/out/users10 --only-summary
```

Set `CACHE_TTL_S=0` in `.env` and restart the backend for the uncached runs. The host is the reverse proxy of `docker-compose.prod.yml`; with the development stack use `http://127.0.0.1:8000`.
