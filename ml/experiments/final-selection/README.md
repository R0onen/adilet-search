# Final reranker selection (15 November 2026)

Measured through the live API (`POST /api/v1/search`, hybrid mode, full 8-code index) on the 195 synthetic **test** questions; `human_ok_*` is the subset of 53 questions a person marked as correct (`data/eval/labeling/synthetic_review.csv`). Labels are automatic: the article a question was written for is the only relevant one. Script: `ml/scripts/eval_api_synthetic.py`; rows: `api_eval.jsonl`.

| Reranker | Candidates | Right article first | MRR@10 | nDCG@10 | Recall@10 | Human-approved: first / nDCG@10 | p50 per search |
|---|---|---|---|---|---|---|---|
| pretrained (0.2.0) | 5 | 0.831 | 0.867 | 0.885 | 0.944 | 0.811 / 0.890 | 254 ms |
| pretrained (0.2.0) | 10 | 0.836 | 0.879 | 0.895 | 0.944 | 0.792 / 0.891 | 454 ms |
| pretrained (0.2.0) | 20 | 0.836 | 0.884 | 0.903 | 0.959 | 0.792 / 0.910 | 963 ms |
| **fine-tuned (1.0.0)** | **5** | **0.851** | 0.880 | 0.895 | 0.944 | 0.830 / 0.902 | 289 ms |
| fine-tuned (1.0.0) | 10 | 0.862 | 0.894 | 0.907 | 0.944 | 0.792 / 0.897 | 535 ms |
| fine-tuned (1.0.0) | 20 | 0.867 | 0.902 | 0.916 | 0.959 | 0.792 / 0.913 | 944 ms |

**Decision.** The fine-tuned reranker (Assignment 4, configuration E3b: trained on the written questions only) is better than the pretrained one at every depth. With 5 candidates it already ranks the right article first more often than the pretrained model does with 20, at a quarter of the time, so pipeline 1.0.0 is the fine-tuned reranker with `rerank_top_n: 5`. A deployment with spare CPU can raise the depth with `SEARCH_RERANK_TOP_N`.

Limits: one test set of 195 questions, so differences of one or two points are within noise (the 53-question human subset moves by 1.9 points per question); latency was measured sequentially on a laptop CPU.
