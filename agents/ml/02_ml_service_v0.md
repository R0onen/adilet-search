# ML-02: ml-service v0 (walking skeleton) and LLM serving (week 2)

**Goal:** by the end of week 2 the Backend can call real zero-shot models through the contract. Quality comes later. The **interface must already have its final shape.**

## Tasks

1. **The service.** Implement `ml/serving/`, a FastAPI app that follows `contracts/ml_service.md` exactly: `GET /health`, `GET /version`, `GET /metrics`, `POST /embed`, `POST /rerank`, `POST /generate` (SSE stream and non-stream). Errors use the contract's error shape and propagate `X-Request-Id`.

2. **Model loading.**
   - The service reads `ml/models/model_manifest.json` (path from env `MODEL_MANIFEST_PATH`).
   - Weights go to `MODEL_CACHE_DIR` (a mounted volume). `ml/scripts/fetch_models.py` downloads the pinned revisions. **Weights are never baked into the image.**
   - Load models once at startup. `/health` reports `down` until they are loaded.

3. **v0 components** (`pipeline_version` 0.1.0):
   - **Embedder:** `intfloat/multilingual-e5-base`, zero-shot. Apply the `query: ` / `passage: ` prefixes inside the service, normalise the vectors, and batch internally.
   - **Sparse encoder:** BM25 term weights.
     - RU: Snowball stemming + stopwords. KK: lowercase + a simple tokeniser for now; note it as a known limitation.
     - Tokens map to stable uint32 indices: a fixed hash or a saved vocabulary.
     - Passages get BM25 TF saturation with `k1`, `b` and `avgdl` from the manifest. Queries get 1.0 per unique term.
     - IDF is applied by Qdrant (`qdrant_idf_modifier: true`). Use the same tokeniser for passages and queries.
     - Save the artifact (vocabulary/params) with a version that feeds `index_compat_id`.
   - **Reranker:** a small multilingual cross-encoder, e.g. `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`. Verify that it loads and measure its CPU latency on 30 candidates.
   - **Generator:**
     - Calls an OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`).
     - Provide the `llm` service: the llama.cpp server image plus a GGUF (Q4_K_M) of an instruct model with good Russian, small enough for CPU (try ~3B first and record its speed).
     - Document in `ml/serving/README.md` how to point at an external GPU endpoint instead.

4. **Prompt template `ml/prompts/answer_v1.md`** (a system part and a user part). Its rules:
   - answer **only** from the numbered sources;
   - put `[n]` after every claim;
   - reply in the question's language;
   - if the sources do not answer the question, say so plainly and do not guess;
   - no personal legal advice, no invented article numbers;
   - at most ~200 words.

   The service fills the template from the `/generate` sources.

5. **Fusion fixture.**
   - Implement `adilet_ml.retrieval.fusion.rrf` (the contract §2 algorithm, including collapse to articles).
   - Write `contracts/fixtures/fusion_cases.json` with at least 6 cases:
     - ties;
     - chunks present in only one list;
     - several chunks of one article;
     - unequal weights;
     - empty lists;
     - `keyword` mode.

   The backend tests its own implementation against this file.

6. **Packaging.**
   - `ml/serving/Dockerfile`: CPU-only torch wheels, non-root user, a healthcheck, `MODEL_CACHE_DIR` as a volume.
   - Put a ready-to-paste compose snippet for `ml-service` and `llm` (images, env, volumes, healthchecks, resource limits) in your status file. Backend owns `docker-compose.yml`.

7. **Manifest and docs.** Write `ml/models/model_manifest.json` v0.1.0 (the contract §3 schema, revisions pinned to commit SHAs) and `ml/serving/README.md` with curl examples for every endpoint.

8. **Tests:**
   - request/response schema tests;
   - prefix handling;
   - sparse encoder determinism (same input gives the same output, and indices are stable across processes);
   - SSE event format;
   - `/generate` with a mocked LLM;
   - `/health` before and after loading;
   - the fusion implementation against the fixture.

9. **Benchmarks** (`ml/scripts/bench_latency.py`). On CPU, with the threads limited to 4, record p50/p95 in your status table for:
   - `/embed` with 1 query;
   - `/embed` with 64 passages;
   - `/rerank` with 30 candidates;
   - `/generate` TTFT and tokens/s.

## Acceptance criteria

- [ ] `docker build` and run work, and every curl example in `ml/serving/README.md` succeeds. `/version` returns the manifest.
- [ ] The fusion fixture is committed and its tests pass.
- [ ] Latency numbers are in the status file. If `/embed` or `/rerank` already exceed the contract budget, say so and propose a fix.
- [ ] Backend has been told the image name, env vars, compose snippet and measured latencies.

## Also start now (human-heavy, long lead time)

Draft the first 100 gold query candidates for ML-03 Part A and give them to the humans for editing. Labelling takes calendar time.
