# Does training on the added acts help the reranker? (16–20 November 2026)

**Question.** The served reranker (Assignment 4, E3b) was fine-tuned on questions about the 8 main codes only, while the deployed index holds 40 acts. On everyday questions about the 32 added acts the live search puts the right article first for 58%, against 83% on the synthetic questions about the 8 codes. Is the reranker's training data the cause?

**Experiment.** `ml/scripts/train_reranker.py` repeats E3b exactly (same base model, input, learning rate 1e-5, batch 32, 7 random negatives from the top-20 BM25 candidates, best epoch by validation nDCG@10) with 527 more training questions about the added acts (`data/eval/synthetic_t2/`: 632 LLM-written questions for 320 articles of 31 acts, split by article; the articles of the everyday set are excluded). Candidates for training come from BM25 over the 40 acts. 8,128 training pairs, 224 validation questions, 1 epoch selected (validation nDCG@10 fell after it), 4 minutes on an RTX 4060 Laptop GPU.

**Results** (`results.json`; offline, BM25 top-20 candidates, reranked):

| Test set | Ceiling | E3b (served) | New (40 acts) | Difference (95% CI, p) | Better / worse |
|---|---|---|---|---|---|
| 195 synthetic test questions, 8 codes (as in A4) | 0.923 | nDCG@10 0.880, first 0.826 | 0.885, 0.836 | +0.004 (−0.005 … +0.014, p = 0.40) | 8 / 5 |
| 55 everyday questions, added acts | 0.655 | nDCG@10 0.535, first 0.436 | 0.524, 0.400 | −0.011 (−0.046 … +0.020, p = 0.56) | 3 / 4 |

**Through the live API** (hybrid search: dense and BM25 candidates fused, 5 reranked, the deployed 40-act index; `api_eval.jsonl`, `api_everyday.jsonl`):

| Test set | Served (E3b) | New (40 acts) |
|---|---|---|
| 195 synthetic test questions: right article first / nDCG@10 | 0.826 / 0.874 | 0.815 / 0.870 |
| 55 everyday questions: first / top 3 / top 10 | 0.582 / 0.745 / 0.873 | 0.582 / 0.745 / 0.873 |

On the everyday questions the new model moves 3 questions up and 3 down; the totals are identical.

**Answer: no.** Neither difference is significant. More training questions about the added acts do not make the reranker better on everyday questions about them. The limit is elsewhere:

- **Retrieval.** BM25 has a labelled article among its 20 candidates for only 65% of the everyday questions (92% for the synthetic ones); no reranker can fix the other 35%. The live hybrid search does better (87% in the top 10) because the dense embedder finds articles without shared words.
- **Question style.** The everyday questions are shorter and more colloquial than the LLM-written training questions. Training data in the users' own wording, not more of the same synthetic kind, is what would test this further.

**Decision.** The served reranker stays E3b (pipeline 1.0.0). The new checkpoint is not published.

**Also found.** 22 question ids of the original training split were used twice (`data/eval/synthetic/`), which paired 44 training questions with a wrong article in A3/A4. Fixed before this run; test and validation were never affected (see the A3 and A4 reports).

**Limits.** The everyday set has 55 questions written inside the project; one seed.
