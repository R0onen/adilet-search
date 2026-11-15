# Final evaluation

Measured on 15 November 2026 through the running API (`docker-compose.prod.yml`, pipeline 1.0.0), so the numbers include everything a user's request goes through: query expansion, dense and sparse retrieval in Qdrant, fusion, collapsing chunks to articles, and reranking of the first 5 articles.

## Test set

- 195 test questions from `data/eval/synthetic/`, written by an LLM for articles of the 8 main codes; 41% Kazakh; half in everyday wording, half in legal terminology. Their articles were not used in training.
- The label is automatic: the article a question was written for is the only relevant one. Another article that also answers the question counts as an error.
- A person reviewed 60 of the questions: 53 correct, 3 with the wrong article, 4 too vague (`data/eval/labeling/synthetic_review.csv`). The "human-approved" columns below use those 53.

## Search

| Index | Reranker | Candidates reranked | Right article first | MRR@10 | nDCG@10 | Recall@10 | Human-approved: first / nDCG@10 | p50 per search |
|---|---|---|---|---|---|---|---|---|
| 8 codes | pretrained (0.2.0) | 5 | 0.831 | 0.867 | 0.885 | 0.944 | 0.811 / 0.890 | 254 ms |
| 8 codes | fine-tuned (1.0.0) | 5 | 0.851 | 0.880 | 0.895 | 0.944 | 0.830 / 0.902 | 289 ms |
| 8 codes | fine-tuned (1.0.0) | 20 | 0.867 | 0.902 | 0.916 | 0.959 | 0.792 / 0.913 | 944 ms |
| **40 acts (deployed)** | **fine-tuned (1.0.0)** | **5** | **0.826** | 0.854 | 0.871 | 0.928 | 0.830 / 0.908 | 357 ms |
| 40 acts | fine-tuned (1.0.0) | 10 | 0.856 | 0.890 | 0.901 | 0.933 | 0.792 / 0.900 | 548 ms |
| 291 acts | fine-tuned (1.0.0) | 5 | 0.795 | 0.836 | 0.858 | 0.928 | 0.830 / 0.902 | 352 ms |

Rows: `ml/experiments/final-selection/api_eval.jsonl`. Script: `ml/scripts/eval_api_synthetic.py`. Latency is one request at a time on a laptop CPU.

What the table says:

1. **The fine-tuned reranker is better than the pretrained one** at the same depth: +2.0 points of "right article first" on the 8 codes. The offline comparison on the same questions is significant (+0.013 nDCG@10, p = 0.016, `A4_report.md`).
2. **A larger corpus costs a little accuracy on these questions.** From 8 codes to 40 acts: −2.5 points; to 291 acts: −5.6 points. The questions were written for the 8 codes, and other acts regulate the same subjects, so an article of another act is often a reasonable answer that the automatic label counts as wrong. On the human-approved questions the result is the same on all three indexes (0.830).
3. **The deployed index is the 40 acts.** It answers everyday questions about family, consumer, housing, traffic and enforcement law that the 8 codes cannot, at a small cost; the 291 acts add mostly specialised laws and cost more.
4. **Reranking 10 instead of 5** would add 3 points on the deployed index and halve the throughput. The default stays 5 so that 10 concurrent users are served on a CPU (`load_test.md`); `SEARCH_RERANK_TOP_N` changes it.

### Query expansion

The dictionary of everyday words (`backend/app/services/query_expansion.py`) does not change the result on the 195 test questions (0.826 and 0.871 with and without it): LLM-written questions rarely use colloquial words. Its effect shows on hand-written everyday questions (`docs/presentation/demo_questions.md`): of 10 questions, the expected article is first for 7 and in the top 4 for all 10. Before the dictionary, "работодатель задерживает зарплату — что делать?" and "можно ли вернуть товар в магазин без чека" returned unrelated articles first and did not have the expected article in the top 5. Ten hand-picked questions are an illustration, not a measurement.

## Generated answers

30 human-approved test questions (all Russian) were sent to `POST /api/v1/answer` with the hosted LLM (`qwen/qwen3.8-27b`, 5 sources). Script: `ml/scripts/eval_api_answers.py`, run on 15 November 2026.

| | Count |
|---|---|
| Questions | 30 |
| Answer generated | 29 (1 failed at the LLM provider) |
| Labelled article among the 5 sources | 26 of the 29 |
| Answer cites the labelled article, when it was among the sources | 26 of 26 |
| Direct answer with valid citations (`grounded: true`) | 25 |
| "No direct answer" opening, followed by what the sources say | 4 |
| Citations to a source that was not provided (removed by the backend) | 0 |
| Time to the first word (includes search) | p50 0.8 s |
| Whole answer | p50 1.3 s |

How this was reached. A first run exposed two defects, both fixed before the run above:

- 17 of 30 answers failed. The provider allows 8,000 tokens a minute: the questions arrived faster than that, and five long articles in one request exceeded the limit on their own. The backend now caps the source text of one answer at 10,000 characters and sends the matched passage of a long article instead of its beginning; the ML service waits and retries once when it is rate-limited.
- 9 of 13 generated answers opened with "no direct answer" although the cited article answered the question. The prompt now reserves that opening for questions whose rule no source states.

What the numbers do not show: nobody has judged whether each statement follows from the cited article. In the 4 "no direct answer" cases the sources list several cases (different fines or time limits by situation) and the model treats that as indirect; two of them could be answered directly. The provider's free tier allows 8,000 tokens a minute and 200,000 a day: about two answers a minute and 50 a day. Search is not affected by these limits.

The table is from the run made before the last prompt rule was added (a partial answer must not carry the "no direct answer" sentence). A repeat with the final prompt ran into the daily token limit after 16 answers (13 direct, 3 with the opening; all 15 that had the labelled article among the sources cited it), so it is not reported as a result and the per-answer file is not committed. One full run costs about 120,000 tokens.

## Speed

| | |
|---|---|
| One search, deployed index | p50 357 ms, p95 530 ms |
| 10 concurrent users, cache off | p50 650 ms, p95 1.2 s, 0 failed, 1 of 981 without reranking (`load_test.md`) |

## Limits

- LLM-written questions and automatic labels; 195 questions, so differences under about 2 points are within noise. On the 53 human-approved questions one question is 1.9 points.
- No lawyer has judged the results or the answers.
- The questions cover the 8 codes only. There is no test set for the 32 added acts beyond the ten everyday questions.
- Kazakh questions are answered less well than Russian ones (offline reranker nDCG@10 0.83 against 0.91).
