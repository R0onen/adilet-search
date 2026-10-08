# Internal ML service contract (v1)

- **Owner:** ML.
- **Consumer:** Backend (and ML's own evaluation scripts).
- **Address in compose:** `http://ml-service:8001`. Internal only; never exposed through Caddy.

The service hides every model detail from the backend: prefixes, tokenisation, sparse encoding, prompt building and the choice of LLM. The backend sends raw text and gets vectors, scores or a token stream back.

---

## 1. Endpoints

### `GET /health`

```json
{"status": "ok", "components": {"embedder": "ok", "sparse": "ok", "reranker": "ok", "generator": "unavailable"}, "pipeline_version": "0.1.0"}
```
- `status` is one of `ok | degraded | down`.
- `generator` reflects whether the LLM endpoint is reachable (checked at most every 10 s).
- HTTP 200 for `ok`/`degraded`, 503 for `down`.

### `GET /version`

Returns the full model manifest (§3).

### `GET /metrics`

Prometheus metrics. Must include `ml_request_duration_seconds{endpoint}` (histogram), `ml_requests_total{endpoint,status}`, `ml_generate_ttft_seconds` (histogram) and `ml_batch_size{endpoint}` (histogram).

### `POST /embed`

```json
{"texts": ["Ответственность работодателя за задержку зарплаты"], "kind": "query", "return_dense": true, "return_sparse": true}
```
- `kind` is `query` or `passage`. The service applies model-specific prefixes itself (e.g. E5's `query: ` / `passage: `). **Callers send raw text.**
- Up to 128 texts per call, each at most 8000 chars. Longer inputs are truncated to the model's `max_seq_len`, and `truncated[i]` is set to `true`.

Response:
```json
{
  "dense": [[0.0123, -0.0456, "…"]],
  "sparse": [{"indices": [1834, 99012, 400223], "values": [1.0, 1.0, 1.0]}],
  "dim": 768,
  "truncated": [false],
  "model_version": "0.1.0"
}
```
- Dense vectors are L2-normalised floats of length `dim`.
- Sparse vectors are opaque to the backend: it passes them to Qdrant unchanged. Indices are uint32, stable for a given `index_compat_id`. Values are BM25 term weights *without* IDF, because Qdrant applies IDF (the sparse vector is configured with `modifier: idf`).
- `dense` or `sparse` is `null` when not requested.

### `POST /rerank`

```json
{"query": "…", "candidates": [{"id": "K1500000414:ru:a113", "text": "<text_for_embedding of the best chunk>"}], "top_n": null}
```
Accepts up to 100 candidates. `top_n: null` means return all of them.

Response:
```json
{"results": [{"id": "K1500000414:ru:a113", "score": 7.21}], "model_version": "0.1.0"}
```
Results are sorted by score, descending. Scores are comparable only within one call.

### `POST /generate`

```json
{
  "question": "Ответственность работодателя за задержку зарплаты",
  "lang": "ru",
  "sources": [{"ref": 1, "article_id": "K1500000414:ru:a113", "title": "Трудовой кодекс РК. Статья 113. …", "text": "<full article text, already truncated by backend to max_chars_per_context>"}],
  "max_tokens": 512,
  "temperature": 0.1,
  "stream": true
}
```

**Input limits.** At most 8 sources; `max_tokens` at most 1024.

**What the service does.** It fills the prompt template named in the manifest and calls the LLM over the OpenAI-compatible API configured by the env vars `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`. The answer is in `lang` and cites sources as `[n]`.

**Streaming response** (`stream: true`, `text/event-stream`):
```
event: token
data: {"text": "Работодатель "}

event: done
data: {"text": "<full text>", "finish_reason": "stop", "usage": {"prompt_tokens": 2310, "completion_tokens": 188}, "ttft_ms": 1450, "total_ms": 5200, "model_version": "0.1.0"}
```
On failure the service emits `event: error` with `data: {"code": "llm_unavailable" | "llm_timeout" | "internal_error", "message": "…"}`.

**Non-streaming response** (`stream: false`): a JSON object with the same fields as the `done` data.

### Errors

Errors use the same shape as the public API: `{"error": {"code", "message", "details", "request_id"}}`. The backend propagates `X-Request-Id`.

---

## 2. Fusion and candidate selection (normative)

The ML experiments and the backend both implement this exactly. `contracts/fixtures/fusion_cases.json` (written by ML in phase ML-02) holds test cases, and the backend's unit tests must pass on them.

1. **Retrieve.** Each retriever `s ∈ {dense, sparse}` returns a list of chunk ids ranked 1-based, truncated to `retrieval.dense_limit` / `retrieval.sparse_limit`.
2. **Fuse (weighted RRF).**

   `F(c) = Σ_s  w_s / (k + rank_s(c))`

   - The sum runs only over the lists that contain `c`.
   - `k = retrieval.rrf_k`, `w_dense = retrieval.weights.dense`, `w_sparse = retrieval.weights.sparse`.
3. **Sort** by `F` descending. Break ties by the better (lower) dense rank, with chunks missing from the dense list counting as worst; then by `chunk_id` ascending.
4. **Collapse to articles.** An article's score is the max `F` over its chunks, and its best chunk is the argmax. Keep the order from step 3.
5. **Rerank.** Send the first `retrieval.rerank_top_n` articles to `/rerank`, each with `text = text_for_embedding` of its best chunk. The final order is the reranker score, descending; ties keep the fused order. Articles beyond `rerank_top_n` follow in fused order.
6. **Modes.**
   - `semantic`: the dense list only, then steps 4–5.
   - `keyword`: the sparse list only, then step 4; **no** rerank.
   - Degraded mode (reranker failed or timed out): the step 4 order, with `score_type: fusion`.

---

## 3. Model manifest: `ml/models/model_manifest.json`

The backend reads it at startup, from the path in `MODEL_MANIFEST_PATH` or from `GET /version` (env `MANIFEST_SOURCE=file|service`).

```json
{
  "pipeline_version": "0.1.0",
  "created_at": "2026-10-12",
  "index_compat_id": "e5base-bm25ru-ch1",
  "embedder": {
    "id": "e5-base-zs",
    "hf_repo": "intfloat/multilingual-e5-base",
    "revision": "<commit sha>",
    "dim": 768,
    "distance": "cosine",
    "max_seq_len": 512,
    "query_prefix": "query: ",
    "passage_prefix": "passage: ",
    "runtime": "torch"
  },
  "sparse": {
    "id": "bm25-ru-snowball-v1",
    "type": "bm25",
    "qdrant_idf_modifier": true,
    "params": {"k1": 1.2, "b": 0.75, "avgdl": 142.3}
  },
  "reranker": {
    "id": "mmarco-mminilm-zs",
    "hf_repo": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "revision": "<commit sha>",
    "max_seq_len": 512,
    "runtime": "torch"
  },
  "generator": {
    "id": "base-instruct-q4",
    "base_model": "<hf repo of the base LLM>",
    "adapter": null,
    "gguf": "<hf repo/file of the GGUF used by llama.cpp>",
    "served_model_name": "adilet-generator",
    "prompt_template": "prompts/answer_v1.md",
    "max_context_tokens": 6000
  },
  "retrieval": {
    "dense_limit": 50,
    "sparse_limit": 50,
    "rrf_k": 60,
    "weights": {"dense": 1.0, "sparse": 1.0},
    "rerank_top_n": 30,
    "default_top_k": 10,
    "context_top_k": 5,
    "max_chars_per_context": 4000
  },
  "chunking": {"version": "ch1", "max_chunk_tokens": 400, "tokenizer": "intfloat/multilingual-e5-base"},
  "corpus_version": "2026.10.10",
  "eval": {"dataset": "gold_test@splits_v1", "ndcg@10": null, "recall@10": null, "mrr@10": null}
}
```

### Versioning rules

| What changes | Version bump | Reindex needed? |
|---|---|---|
| embedder, sparse encoder or chunking | new `pipeline_version` **and** new `index_compat_id` | yes, into a new collection |
| reranker, generator, prompt or retrieval params only | new `pipeline_version`; `index_compat_id` unchanged | no |
| breaking change to this contract's endpoints | major version | — |

The backend records the `index_compat_id` of each Qdrant collection it builds. If it does not match the manifest, the backend refuses dense search (degraded: `semantic`) and the admin system page shows "reindex required".

---

## 4. Performance budgets (4 vCPU, no GPU)

| Call | p95 target |
|---|---|
| `/embed`, 1 query | ≤ 150 ms |
| `/embed`, 64 passages | measured and reported (used only for indexing) |
| `/rerank`, 30 candidates | ≤ 900 ms |
| `/generate` | TTFT and tokens/s measured and reported; no hard target on CPU |

The ML agent reports measured values in `docs/status/ml.md` every time the manifest changes.
