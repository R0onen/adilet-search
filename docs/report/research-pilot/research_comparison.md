# Research comparison

title-derived proxy labels; body-only corpus; pilot is not confirmatory

Exploratory pilot; too small to establish general retrieval quality.

| Method | Val nDCG@10 | Test nDCG@10 | RU test | KK test | Test MRR@10 |
|---|---:|---:|---:|---:|---:|
| e5 | 0.616 | 0.715 | 0.750 | 0.680 | 0.668 |
| current_hybrid_reranker | 0.875 | 0.875 | 0.750 | 1.000 | 0.875 |
| hybrid_no_reranker | 0.750 | 0.774 | 0.733 | 0.815 | 0.698 |
| e5_llm_rewrite | 0.611 | 0.670 | 0.750 | 0.589 | 0.646 |
| qwen3 | 0.496 | 0.315 | 0.472 | 0.158 | 0.254 |
| bge_m3 | 0.670 | 0.737 | 0.750 | 0.723 | 0.646 |

Validation-selected candidate: current_hybrid_reranker

These are our measured results, not numbers copied from model leaderboards.

The hybrid row reproduces the project's stages on body-only chunks with local BM25; its IDF differs from Qdrant.

current_hybrid_reranker: paired test delta +0.160, bootstrap 95% CI [+0.000, +0.320].

hybrid_no_reranker: paired test delta +0.059, bootstrap 95% CI [-0.157, +0.273].

e5_llm_rewrite: paired test delta -0.045, bootstrap 95% CI [-0.125, +0.000].

qwen3: paired test delta -0.400, bootstrap 95% CI [-0.496, -0.248].

bge_m3: paired test delta +0.022, bootstrap 95% CI [-0.295, +0.299].

Exploratory current_hybrid_reranker_vs_bge_m3: +0.138, 95% CI [-0.033, +0.326]; no multiplicity correction.

Exploratory current_hybrid_reranker_vs_hybrid_no_reranker: +0.101, 95% CI [-0.015, +0.217]; no multiplicity correction.
