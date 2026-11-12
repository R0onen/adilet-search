# Research study: multilingual legal retrieval

The midterm feedback identified an engineering-heavy project. The final study therefore treats
Adilet Search as a testbed for explicit research questions, rather than counting UI features.

## Questions and hypotheses

1. Does a newer instruction-based embedding model improve article retrieval over multilingual
   E5 on Russian and Kazakh legislation? Compare E5, Qwen3-Embedding-0.6B,
   EmbeddingGemma 2 and BGE-M3.
2. Does the project's hybrid retrieval and cross-encoder improve over dense retrieval alone?
   Use a body-only offline reproduction of its fusion/reranking stages.
3. Does an LLM rewrite improve E5 retrieval sufficiently to justify its extra latency and
   external service dependency? Compare the exact same questions before and after rewriting.
4. Are gains consistent across RU and KK? Report both languages separately and inspect failures.

These are hypotheses to test. A negative result is an acceptable research finding.

## Candidate selection and sources

- Existing model: `intfloat/multilingual-e5-base`, pinned to its resolved HF commit.
- Recent text-focused challenger: `Qwen/Qwen3-Embedding-0.6B`; use its instruction-aware query
  format and unprefixed passages. [Official model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).
- Late-2026 challenger: `google/embeddinggemma-2` (6 October 2026), with only its text encoder loaded.
  Use the official search/document prefixes with `title: none`, BF16 (or FP32), never FP16.
  [Official model card](https://huggingface.co/google/embeddinggemma-2).
- Established multilingual control: `BAAI/bge-m3`; this is a control, not a claim of recency.
- LLM ablation: the already configured external `LLM_MODEL`, recorded in every result.
  The query rewrite receives only the query, never sources, article IDs or qrels.
- Newer multimodal work was also reviewed: [Qwen3-VL Embedding](https://qwen.ai/blog?id=qwen3-vl-embedding).
  It is not implemented by the text-only SentenceTransformer runner. Do not describe this study
  as an exhaustive comparison of the newest available models.

## Controlled protocol

- Same full corpus and same body chunks for every method; do not embed article-title headers.
- Same existing group-based validation/test splits; RU/KK versions of an article remain grouped.
- Fix the common maximum input at 512 model tokens and normalized cosine retrieval. Each model
  uses its own documented query formatting. Different tokenizers may retain different amounts
  of text; this is a limitation of the common token budget.
- Rank chunks, then collapse to distinct articles. Primary metric: nDCG@10. Also report MRR@10,
  Recall@10 and Recall@50, overall and by language.
- Select a candidate using validation nDCG@10. Report held-out test results without tuning on them.
- Compute paired bootstrap confidence intervals on test nDCG differences against E5
  (2,000 resamples, seed 42), resampling article families so parallel RU/KK queries stay together. Queries with one known relevant article do not describe all possible
  relevant answers; report this limitation.
- Record checkpoint revisions, dataset fingerprints, rankings, hardware, precision, cache use
  and timing. Encoding/ranking throughput is not an API p95 measurement.
- Run models sequentially on the GPU, keeping deployment model weights separate from research
  caches. The research code does not replace the serving manifest or production index.

## Dataset limitation

The current 8,735 queries are official article titles with proxy relevance labels. Removing
headers avoids the most direct title-to-header shortcut, but does not make them realistic user
questions. They favour statutory language. Use them for exploratory comparison and explicitly
label the results. A publishable or general natural-language conclusion requires a separate,
human-reviewed RU/KK benchmark. An LLM rewrite is an experimental treatment, not gold labeling.

## Implementation and artifacts

`ml/scripts/research_benchmark.py` runs E5, Qwen3, BGE-M3, the hybrid/reranker reproduction and
the optional LLM rewrite ablation. The hybrid reproduction uses local BM25 on body chunks;
its IDF differs from the deployed Qdrant sparse index. Keep that distinction in the report.

The GPU image already includes the required pinned model libraries. Copy the script, the
processed chunks and the three evaluation files into a temporary research directory, then run:

```bash
python research_benchmark.py --data DATA_DIR --eval EVAL_DIR --out OUTPUT_DIR --llm-rewrite
```

`--pilot-per-language 4` runs a small implementation pilot (four queries per language per split)
against the full corpus. The pilot is balanced by language/split but follows query-ID order, not an act-stratified random sample.
It is not a completed confirmatory experiment. Default zero uses all
frozen validation/test queries. Model vector caches and rewrite responses are reusable.

Outputs include `results.json`, per-method article rankings, cached rewrites and corpus vectors.
Store vectors in ignored data directories, not Git. Report actual completed runs only. Model
access failures, rate limits and out-of-memory errors must remain visible; never substitute
another model silently or fabricate comparison rows.

## Presentation changes after execution

Replace feature lists with: research questions → controlled protocol → metric table by language
→ paired differences and uncertainty → representative failure cases → limitations. Keep one
architecture slide and a short demo as the application of the findings. Do not announce a
winning model before the experiment finishes.

Research inference uses FP16 for E5/Qwen3/BGE-M3 and the publisher-required BF16 (or FP32) for EmbeddingGemma 2; stored vectors are FP32.
The deployed E5 model may use another precision; this controlled comparison reports its own
measurements rather than treating encoder-only timings as deployment performance.

Precision and architecture both vary: this evaluates practical pretrained model configurations,
not the isolated causal effect of release date or architecture. Numerical validity checks reject
NaN and degenerate vectors.
