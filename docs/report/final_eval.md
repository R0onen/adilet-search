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

## Everyday questions about the added acts

The 195 test questions cover only the 8 codes. For the 32 added acts there is a second, small set: 55 questions in everyday wording (45 Russian, 10 Kazakh) about 24 of those acts, each labelled with the one or two articles that answer it (`data/eval/everyday/`). The articles were picked from the corpus by title without using the search system; the questions were written with an LLM assistant and nobody outside the project has reviewed them.

| Search | Reranked | Right article first | In the top 3 | In the top 10 | MRR@10 |
|---|---|---|---|---|---|
| keyword only (PostgreSQL full-text) | – | 0.255 | 0.400 | 0.636 | 0.360 |
| **hybrid, deployed** | **5** | **0.582** | 0.745 | 0.873 | 0.674 |
| hybrid | 10 | 0.618 | 0.818 | 0.873 | 0.722 |

Rows: `ml/experiments/final-selection/everyday_eval.jsonl`. Script: `ml/scripts/eval_api_everyday.py`.

- Hybrid search finds the right article first more than twice as often as keyword search, and has it in the top 10 for 87% of the questions.
- This is clearly below the 83% on the synthetic questions. These questions are shorter and more colloquial, the acts were not in the reranker's training data, and several of them have many similar articles (the three procedure codes, the enforcement law).
- In 7 of the 55 questions the right article is retrieved at rank 6–10, beyond the 5 that are reranked. Reranking 10 moves it up (top 3: 75% → 82%) at about half the throughput.
- 7 questions do not have the right article in the top 10 at all, 5 of them about enforcement proceedings and mortgage: retrieval, not reranking, is the limit there.
- Kazakh: 7 of 10 first. Ten questions are too few to compare the languages.

**Is the reranker's training the cause?** No. Retraining it with 527 more LLM-written questions about the added acts left both test sets unchanged: offline nDCG@10 0.880 → 0.885 on the 195 synthetic questions (p = 0.40) and 0.535 → 0.524 on the 55 everyday questions (p = 0.56); through the live hybrid search the everyday result is identical (58% first, 87% in the top 10) and the synthetic one slightly lower (82.6% → 81.5% first). The served reranker stays as it is; details in `ml/experiments/reranker-40acts/`. The gap comes from retrieval (BM25 has the article among its 20 candidates for only 65% of the everyday questions) and from the questions' colloquial wording.

## Generated answers

Questions were sent to `POST /api/v1/answer` with the hosted LLM (`qwen/qwen3.8-27b`, 5 sources) on 16 November 2026. Script: `ml/scripts/eval_api_answers.py`; every answer is saved in `ml/experiments/final-selection/answers.jsonl` (Russian) and `answers_kk.jsonl` (Kazakh) for reading.

| | 30 human-approved test questions (Russian) | 10 everyday questions (Kazakh) |
|---|---|---|
| Answer generated | 28 (2 failed at the LLM provider) | 10 |
| A labelled article among the 5 sources | 25 of 28 | 8 of 10 |
| Answer cites it, when it was among the sources | 25 of 25 | 8 of 8 |
| Direct answer with valid citations (`grounded: true`) | 19 | 8 |
| Opens with "no direct answer", then reports what the sources say | 9 | 2 |
| Citations to a source that was not provided | 0 | 0 |
| Time to the first word (includes search), p50 | 1.0 s | 1.9 s |
| Whole answer, p50 | 1.6 s | 2.8 s |

What holds: when the right article is retrieved, the answer cites it, every time; no answer cited a source it was not given; Kazakh questions get Kazakh answers.

What does not hold yet: the "no direct answer" opening is overused. In 6 of the 9 Russian cases the labelled article was among the sources and the text after the opening does answer the question, so the answer is right but is marked as not grounded and the UI shows a notice. One Kazakh answer used the Russian version of the sentence. The prompt was restructured after this run (the model first decides whether any source answers, and the opening is allowed only if none does). The first two of the affected questions then got direct answers; the rest could not be re-asked because the provider's daily token limit was reached. The table is therefore from the prompt before that last change.

Earlier defects, found by the first run of this check and fixed before the run above: 17 of 30 answers failed because five long articles in one request exceeded the provider's 8,000 tokens a minute (the backend now caps the source text of an answer at 10,000 characters and sends the matched passage of a long article; the ML service waits and retries once when rate-limited); and 9 of 13 answers carried the opening.

Limits: nobody has judged whether each statement follows from the cited article. The provider's free tier allows 8,000 tokens a minute and 200,000 a day: about two answers a minute and 50 a day. Search is not affected.

## Speed

| | |
|---|---|
| One search, deployed index | p50 357 ms, p95 530 ms |
| 10 concurrent users, cache off | p50 650 ms, p95 1.2 s, 0 failed, 1 of 981 without reranking (`load_test.md`) |

## Limits

- LLM-written questions and automatic labels; 195 questions, so differences under about 2 points are within noise. On the 53 human-approved questions one question is 1.9 points.
- No lawyer has judged the results or the answers.
- The 195 questions cover the 8 codes only. The 55 everyday questions about the added acts were written inside the project and are a sanity check, not a benchmark.
- Kazakh questions are answered less well than Russian ones (offline reranker nDCG@10 0.83 against 0.91).
