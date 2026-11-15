# Infrastructure sizing

What the system needs to run, from measurements on the development machine (Intel Core i7-13700HX, Docker Desktop on Windows, CPU only; 15 November 2026). Numbers for a 4 vCPU server are estimates and are marked as such.

## Measured footprint (full corpus: 9,259 articles, 16,264 chunks)

| Component | RAM in use | Disk | Notes |
|---|---|---|---|
| ML service (embedder + reranker) | 1.2 GiB idle, up to 3.8 GiB under load | 1.6 GB model cache, 2.3 GB image | the peak was with PyTorch using all cores; the compose limit is 5 GiB |
| Qdrant | 0.7–1.2 GiB | 131 MB for the live collection, the same again for each kept old collection or snapshot | 768-dimensional dense vectors plus sparse vectors |
| PostgreSQL | 0.1–0.2 GiB | 227 MB (articles, 13 k logged queries) | a compressed dump is 13 MB |
| Backend | 0.1–0.4 GiB | 0.7 GB image | one process |
| Frontend, Caddy | 30 MiB together | 0.1 GB image | static files and the proxy |
| Prometheus, Grafana | 0.3 GiB together | under 100 MB | 7–15 days of metrics |
| **Total** | **about 3 GiB idle, 6 GiB under load** | **about 8 GB** with images | |

## Deployed corpus (40 acts: 20,490 articles, 41,074 chunks)

The table above was measured on the 8-code corpus. With the deployed 40-act index and pipeline 1.0.0, measured idle after the load test:

| Component | RAM in use | Disk |
|---|---|---|
| ML service | 1.3 GiB | the same images and cache, plus 470 MB for the fine-tuned reranker |
| Qdrant | 0.8 GiB | 291 MB for the live collection |
| PostgreSQL | 0.2 GiB | 232 MB |

The server recommendation below does not change. Indexing this corpus took 17 minutes with the ML service on an 8 GB GPU (about 40 chunks per second) and an estimated 2 hours on CPU, which is why the index is built once and copied to the server (`scripts/transfer_index.sh`).

## Throughput (see `docs/report/load_test.md`)

- 10 concurrent users (about 4 searches per second, nothing cached): p95 0.9–1.0 s on the 8-code index with no degraded responses; p95 1.2 s on the 40-act index with 1 degraded response in 981.
- About 4 uncached searches per second is the ceiling on this CPU: the reranker takes 80% of a request.
- Indexing the 8-code corpus on CPU: 45 minutes (about 340 chunks per minute).

## Recommended server

| | Minimum (demo, a few users) | Recommended (pilot, tens of users) |
|---|---|---|
| CPU | 4 vCPU | 8 vCPU |
| RAM | 8 GB | 16 GB |
| Disk | 40 GB SSD | 80 GB SSD |
| GPU | none | optional: one 8 GB GPU for the ML service |

- **4 vCPU is an estimate, not a measurement.** The reranker scales with cores up to about 4, so a 4 vCPU server should be close to the measured single-request times (0.2–0.4 s per rerank), with a lower ceiling for concurrent users. Repeat the 10-user run on the real server before quoting it.
- **RAM** is set by the ML service (5 GiB limit) plus Qdrant and PostgreSQL; 8 GB leaves little headroom during a reindex, which is why 16 GB is recommended.
- **A GPU is not required.** It would shorten indexing from 45 minutes to a few and raise the search ceiling; `docker-compose.gpu.yml` is the overlay for it.
- **The answer generator is not on this server.** Answers come from an OpenAI-compatible LLM endpoint. Hosting an LLM locally would need a GPU with 16–24 GB of memory and is outside this sizing.

## Growth

| If | Then |
|---|---|
| the corpus grows 10× (all codes and laws) | Qdrant about 1.5 GB on disk and 2–4 GiB of RAM; indexing about 7 hours on CPU, so index on a GPU |
| searches exceed about 4 per second | faster reranker first (ONNX int8, or a GPU); then a shared cache and more backend processes |
| many answers are generated | the limit is the LLM provider's quota, not this server |
