# Research comparison

Full frozen validation/test split; title-derived proxy labels; body-only corpus

Full frozen split; title labels are not natural-language gold data.

| Method | Val nDCG@10 | Test nDCG@10 | RU test | KK test | Test MRR@10 |
|---|---:|---:|---:|---:|---:|
| e5 | 0.706 | 0.703 | 0.802 | 0.605 | 0.658 |
| current_hybrid_reranker | 0.856 | 0.846 | 0.855 | 0.836 | 0.817 |
| hybrid_no_reranker | 0.778 | 0.770 | 0.816 | 0.724 | 0.725 |
| qwen3 | 0.539 | 0.548 | 0.667 | 0.430 | 0.493 |
| bge_m3 | 0.830 | 0.822 | 0.833 | 0.812 | 0.783 |
| embeddinggemma2 | 0.710 | 0.716 | 0.802 | 0.630 | 0.664 |

Validation-selected candidate: current_hybrid_reranker

These are our measured results, not numbers copied from model leaderboards.

The hybrid row reproduces the project's stages on body-only chunks with local BM25; its IDF differs from Qdrant.

current_hybrid_reranker: paired test delta +0.142, bootstrap 95% CI [+0.123, +0.162].

hybrid_no_reranker: paired test delta +0.067, bootstrap 95% CI [+0.052, +0.082].

qwen3: paired test delta -0.155, bootstrap 95% CI [-0.180, -0.129].

bge_m3: paired test delta +0.119, bootstrap 95% CI [+0.100, +0.138].

embeddinggemma2: paired test delta +0.013, bootstrap 95% CI [-0.006, +0.031].

Exploratory current_hybrid_reranker_vs_bge_m3: +0.024, 95% CI [+0.007, +0.040]; no multiplicity correction.

Exploratory current_hybrid_reranker_vs_hybrid_no_reranker: +0.076, 95% CI [+0.059, +0.091]; no multiplicity correction.
