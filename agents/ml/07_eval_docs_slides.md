# ML-07: End-to-end evaluation through the API, documentation, slides (week 6)

**Goal:** prove that the deployed system matches the offline results, and produce the ML parts of the documentation and of the final presentation.

## Tasks

1. **Evaluate through the API: `ml/eval/eval_api.py --base-url <url>`.**
   - Run the gold test set against `/api/v1/search` in all three modes (`hybrid`, `semantic`, `keyword`).
   - Run a 50-question subset against `/api/v1/answer`, parsing the SSE stream.
   - Compute nDCG@10, Recall@10, MRR@10, the citation metrics, latency p50/p95 and TTFT.
   - Write `docs/report/final_eval.md` plus a JSON file. Use the deployed URL from Backend's status file, or the local compose stack if the deployment isn't ready yet.
   - Compare with the offline numbers and **explain every difference** (e.g. Qdrant's BM25 IDF vs bm25s, chunk collapse, filters, the `in_force_only` default).
   - The `keyword` vs `hybrid` comparison is the headline result for the "Problem" and "Performance" slides.

2. **Quality monitoring loop.**
   - `ml/scripts/feedback_report.py` reads the admin CSV export (`/api/v1/admin/queries/export`).
   - It lists the top zero-result queries and the most negatively rated queries, which are candidates for new gold queries and the next fine-tuning round.
   - Describe the loop: logs → review → new gold queries/labels → retrain → new `pipeline_version` → reindex → `eval_api` → release.

3. **`docs/tech/ml.md`:**
   - the data pipeline;
   - the models and why they were chosen (link to decisions);
   - the training procedure;
   - how to release a new pipeline version: manifest bump → precompute embeddings → reindex into a new collection → `eval_api` against it → alias switch;
   - how to roll back (switch the alias back);
   - the known limitations.

4. **Final presentation sections:** write `docs/presentation/sections/ml.md` (Marp) for these slides:
   1. Problem, with one concrete keyword-search failure, taken from `eval_api` keyword vs hybrid;
   2. Dataset;
   3. Model;
   4. Experimental results: **one** unified table covering A2 → A4 and one chart;
   5. Final model;
   9. the ML half of Performance;
   10. the ML items of Limitations and future work.

   One message per slide, each number with its source in the speaker notes. Put the charts in `docs/presentation/img/`.

5. **Defence prep: `docs/presentation/qa_ml.md`.** 15–20 likely questions with short answers you can defend. For example:
   - Why nDCG@10?
   - Why hybrid?
   - Why this encoder?
   - Why QLoRA rather than full fine-tuning, and what do r and alpha do?
   - How do you avoid hallucinated citations?
   - What happens when the law changes?
   - How good is Kazakh, really?
   - How did you prevent leakage?
   - Is the improvement significant?
   - What would you do with a GPU budget?

## Acceptance criteria

- [ ] `final_eval.md` exists, with the API numbers next to the offline numbers and the differences explained.
- [ ] `docs/tech/ml.md` and `ml/MODEL_CARD.md` are complete and consistent with the manifest.
- [ ] The slide sections and the Q&A file are written. Every number can be traced.
- [ ] The status file says "ML done". List anything left for future work.
