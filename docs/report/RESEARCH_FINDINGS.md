# Adilet Search: recent models and retrieval ablations

Study executed locally on 12 November 2026. This addresses the midterm feedback by turning the prototype into a controlled retrieval experiment.

## Questions and design

Do recent pretrained embeddings improve Russian/Kazakh legal retrieval? Does the project's lexical fusion and reranker help? Does LLM query rewriting help E5?

The complete body-only corpus has 16,264 chunks from 9,259 article-language records. All candidates see the same frozen 1,311 validation and 1,318 test queries. Parallel RU/KK article families remain in one split. Queries are titles with known-item proxy labels, not independently judged everyday questions. The retrieval corpus includes all source articles, as in an open retrieval system; no own fine-tuning is performed.

We compare normalized dense vectors with a 512-token encoder budget, language filters and article-level collapse. E5, Qwen3 and BGE-M3 use FP16; EmbeddingGemma 2 uses publisher-supported BF16 with its text-only encoder. Tokenizers differ. The hybrid control reproduces project fusion (RRF 60, equal weights, top 50 dense/sparse) and reranks 20 candidates using the pinned project cross-encoder. Local BM25 IDF differs from the production Qdrant backend. It is an offline stage reproduction, not an API benchmark. No model-specific prompt/length hyperparameter sweep was performed.

## Full frozen-split measurements

| Method | Val nDCG@10 | Test nDCG@10 | RU test | KK test | Test MRR@10 |
|---|---:|---:|---:|---:|---:|
| e5 | 0.706 | 0.703 | 0.802 | 0.605 | 0.658 |
| current_hybrid_reranker | 0.856 | 0.846 | 0.855 | 0.836 | 0.817 |
| hybrid_no_reranker | 0.778 | 0.770 | 0.816 | 0.724 | 0.725 |
| qwen3 | 0.539 | 0.548 | 0.667 | 0.430 | 0.493 |
| bge_m3 | 0.830 | 0.822 | 0.833 | 0.812 | 0.783 |
| embeddinggemma2 | 0.710 | 0.716 | 0.802 | 0.630 | 0.664 |

Select by validation, then report test performance. The selected configuration is `current_hybrid_reranker`. Against dense E5, its test nDCG@10 difference is +0.142, with a paired article-family bootstrap 95% interval [+0.123, +0.162] (2,000 resamples, seed 42).

BGE-M3's result is evidence that an alternative dense model is worth investigating; the measured newer-model configurations do not automatically replace the project's hybrid approach. Lower scores here do not establish general model inferiority. Length, language, query style, instructions and numerical precision remain possible sources of variation, requiring additional controlled experiments.

Additional pairwise intervals are exploratory, without multiple-comparison correction:

- `current_hybrid_reranker_vs_bge_m3`: +0.024, 95% CI [+0.007, +0.040].
- `current_hybrid_reranker_vs_hybrid_no_reranker`: +0.076, 95% CI [+0.059, +0.091].

## LLM rewrite: separate small pilot

- `e5`: test nDCG@10 0.715 on 8 matched test queries.
- `e5_llm_rewrite`: test nDCG@10 0.670 on 8 matched test queries.

The external `openai/gpt-oss-120b` rewrites only the input query, with no documents, IDs or labels in its prompt. The fixed pilot has four queries per language per split (16 total); it is an implementation check and cannot establish a broad LLM effect. No benefit is established on this pilot. Do not compare its mean directly to the full cohort. This evaluates LLM-assisted retrieval, not generated-answer faithfulness.

## Inspectable ranking failures

Examples below are selected disagreements, not a representative error rate. Rank `>50` means the expected proxy article is absent from the saved top 50.

| Language | Title query | Expected proxy article | E5 rank | Hybrid rank | BGE-M3 rank |
|---|---|---|---:|---:|---:|
| ru | Воспрепятствование получению гражданства Республики Казахстан | `K1400000235:ru:a74` | 18 | 1 | 1 |
| ru | Нарушение правил обеспечения сохранности грузов на железнодорожном, морском, речном и автомобильном транспорте | `K1400000235:ru:a625` | 1 | 13 | 1 |
| kk | Адамды ұрлау | `K1400000226:kk:a125` | 13 | 1 | 1 |
| kk | Әкімшілік айыппұл | `K1400000235:kk:a44` | 24 | 45 | 1 |

Ranking disagreements identify cases for manual review. They do not, by themselves, prove a linguistic cause or that every unlabelled retrieved article is irrelevant.

## Limits and next experiments

1. Collect independently written RU/KK questions and have native speakers judge pooled results. One title-based positive per query misses valid alternative legal sources.
2. Compare longer contexts and alternative query instructions on validation only; reserve a fresh test cohort for confirmation after this exploratory comparison.
3. Scale the matched LLM pilot and measure request cost, latency, failures and semantic intent preservation. Evaluate cited-answer support separately from retrieval.
4. Measure end-to-end GPU/API performance separately. Corpus cache hits and offline query/ranking times are recorded, but do not form a fair API p95 comparison.

The product demo still indexes the Labor Code sample; the research experiment uses the full corpus independently. Public HTTPS hosting and CPU load acceptance remain outstanding. All models are pretrained; no project-specific training is claimed.

## Reproduction and primary sources

See [run instructions](../tech/research_benchmark.md), [protocol](RESEARCH_PROTOCOL.md), [machine-readable results](../../ml/experiments/research-final/results.json), and [executed notebook](../../ml/notebooks/Final_Research_Comparison.ipynb). The results record exact model revisions and corpus/query SHA-256 fingerprints.

- [Qwen3 model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).
- [EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2).
- [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3).
- [Multilingual E5 model card](https://huggingface.co/intfloat/multilingual-e5-base).
