# Final reranker selection (15 November 2026)

Measured through the live API (`POST /api/v1/search`, hybrid mode; the first table is on the 8-code index) on the 195 synthetic **test** questions; `human_ok_*` is the subset of 53 questions a person marked as correct (`data/eval/labeling/synthetic_review.csv`). Labels are automatic: the article a question was written for is the only relevant one. Script: `ml/scripts/eval_api_synthetic.py`; rows: `api_eval.jsonl`.

| Reranker | Candidates | Right article first | MRR@10 | nDCG@10 | Recall@10 | Human-approved: first / nDCG@10 | p50 per search |
|---|---|---|---|---|---|---|---|
| pretrained (0.2.0) | 5 | 0.831 | 0.867 | 0.885 | 0.944 | 0.811 / 0.890 | 254 ms |
| pretrained (0.2.0) | 10 | 0.836 | 0.879 | 0.895 | 0.944 | 0.792 / 0.891 | 454 ms |
| pretrained (0.2.0) | 20 | 0.836 | 0.884 | 0.903 | 0.959 | 0.792 / 0.910 | 963 ms |
| **fine-tuned (1.0.0)** | **5** | **0.851** | 0.880 | 0.895 | 0.944 | 0.830 / 0.902 | 289 ms |
| fine-tuned (1.0.0) | 10 | 0.862 | 0.894 | 0.907 | 0.944 | 0.792 / 0.897 | 535 ms |
| fine-tuned (1.0.0) | 20 | 0.867 | 0.902 | 0.916 | 0.959 | 0.792 / 0.913 | 944 ms |

**Decision.** The fine-tuned reranker (Assignment 4, configuration E3b: trained on the written questions only) is better than the pretrained one at every depth. With 5 candidates it already ranks the right article first more often than the pretrained model does with 20, at a quarter of the time, so pipeline 1.0.0 is the fine-tuned reranker with `rerank_top_n: 5`. A deployment with spare CPU can raise the depth with `SEARCH_RERANK_TOP_N`.

## Corpus size (fine-tuned reranker)

| Index | Candidates | Right article first | MRR@10 | nDCG@10 | Recall@10 | Human-approved: first / nDCG@10 | p50 per search |
|---|---|---|---|---|---|---|---|
| 8 codes | 5 | 0.851 | 0.880 | 0.895 | 0.944 | 0.830 / 0.902 | 289 ms |
| **40 acts (deployed)** | **5** | **0.826** | 0.854 | 0.871 | 0.928 | 0.830 / 0.908 | 344 ms |
| 40 acts | 10 | 0.856 | 0.890 | 0.901 | 0.933 | 0.792 / 0.900 | 548 ms |
| 40 acts, with query expansion | 5 | 0.826 | 0.854 | 0.871 | 0.928 | 0.830 / 0.908 | 357 ms |
| 291 acts | 5 | 0.795 | 0.836 | 0.858 | 0.928 | 0.830 / 0.902 | 352 ms |
| 291 acts | 10 | 0.826 | 0.871 | 0.885 | 0.928 | 0.811 / 0.907 | 542 ms |
| 291 acts | 20 | 0.826 | 0.880 | 0.899 | 0.954 | 0.755 / 0.897 | 1,011 ms |

**Decision.** The deployed index is the 40 acts with 5 reranked candidates: it covers everyday questions outside the 8 codes at a cost of 2.5 points on questions written for the 8 codes, and unchanged results on the human-approved questions. Query expansion does not change these numbers; it is there for colloquial wording (`docs/report/final_eval.md`).

## Generated answers

`ml/scripts/eval_api_answers.py out.jsonl --pause 20` sends 30 human-approved questions to `/answer` and saves each answer. One run uses about 120,000 of the LLM provider's 200,000 free tokens a day. Summary of the run of 15 November in `docs/report/final_eval.md`.

Limits: one test set of 195 questions, so differences of one or two points are within noise (the 53-question human subset moves by 1.9 points per question); latency was measured sequentially on a laptop CPU.
