# ML-06: Final model selection and inference packaging, pipeline v1.0.0 (week 5, second half)

**Goal:** freeze the best pipeline that also meets the latency budget, and make it the one the system serves. This is **task 1 of the final assignment**: pick the best model from earlier experiments, load it, prepare it for inference, make it handle new inputs correctly, pin the model version, and describe its inputs and outputs.

## Tasks

1. **Select under a latency constraint.**
   - Choose by val metrics; confirm once on test.
   - The constraint: on the deployment CPU profile (4 vCPU, threads limited to 4), `/embed` for one query ≤ 150 ms p95 and `/rerank` for 30 candidates ≤ 900 ms p95.
   - Measure every candidate with `ml/scripts/bench_latency.py`.
   - If the best reranker is too slow, try these in order and report the quality cost of each:
     1. ONNX Runtime + dynamic int8 quantisation (Optimum);
     2. `rerank_top_n` 20 instead of 30;
     3. a smaller model.
   - Record the decision, with the quality vs latency table, in `docs/decisions.md`.

2. **Freeze `ml/models/model_manifest.json` v1.0.0:**
   - HF repos with exact revisions (commit SHAs);
   - dims, prefixes, max lengths, runtime (torch/onnx);
   - the retrieval parameters tuned in ML-04: limits, RRF k and weights, `rerank_top_n`, `context_top_k`, `max_chars_per_context`;
   - the prompt template version;
   - the `corpus_version`;
   - the expected offline metrics;
   - a new `index_compat_id` if the embedder or sparse encoder changed.

3. **Package the generator.**
   - Merge the QLoRA adapter into the base model, then export a GGUF (Q4_K_M, plus Q8_0 if RAM allows) for the llama.cpp `llm` service.
   - Also document the GPU path (vLLM serving the base model with `--enable-lora` and the adapter) in `ml/serving/README.md`.
   - Measure TTFT and tokens/s for every path you can run.

4. **Robust inference for new inputs.** The service must handle each of these without crashing, and the tests must cover them:

   | Input | Behaviour |
   |---|---|
   | empty or whitespace-only text | 422 |
   | over-long text | truncated to `max_seq_len`, with `truncated: true` |
   | mixed RU/KK text | handled |
   | Latin transliteration, ALL CAPS, typos | no crash; note the quality effect in the model card |
   | batch over the limit | 422 |
   | non-text garbage | 422 |

   Also: outputs are deterministic for the same input (fixed seeds, eval mode), and `model_version` is in every response.

5. **Precompute embeddings.**
   - Compute passage embeddings for the full corpus on a GPU and write `data/index/embeddings_{pipeline_version}.parquet` (the `data_schema.md` §1 columns).
   - Upload it to HF. The backend indexer can then load it instead of calling `/embed` for ~15k chunks on CPU.
   - Verify that a sample of rows equals what `/embed` returns live (cosine > 0.999).

6. **Model card: `ml/MODEL_CARD.md`.** Sections:
   - purpose and intended users;
   - components, with versions and links;
   - **inputs:** query text, 1–500 chars, RU/KK; passages; the generate payload;
   - **outputs:** vector shapes, score semantics, the streamed text with `[n]` citations and its event format;
   - training data and procedure;
   - offline metrics per language and per query type;
   - latency;
   - limitations: KK quality, corpus coverage, currency of the law, synthetic training queries;
   - ethical and legal notes, with the disclaimer that this is not legal advice;
   - how to reproduce.

7. **Regression guard.** Add `ml/tests/test_regression.py`: on a fixed 30-query gold subset, the served pipeline must reach at least the recorded nDCG@10 minus 0.02. If it is too heavy for CI, mark it `@pytest.mark.slow` and document how to run it manually.

## Acceptance criteria

- [ ] Manifest v1.0.0 is merged, `ml-service` serves it, and `/version` shows it.
- [ ] The latency budget is met, with the numbers in the status file.
- [ ] Precomputed embeddings are on HF and verified.
- [ ] The model card is complete. The robustness tests pass.
- [ ] Backend has been notified: "reindex with v1.0.0", with the location of the precomputed embeddings and whether `index_compat_id` changed.
