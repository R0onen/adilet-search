# ML-03: Evaluation set, splits and baselines (Assignment 2: Data Preparation & Baseline), week 3

**Goal:** a trustworthy evaluation set, and a trained lexical baseline that stands in for today's keyword search. This is the bar every later model must beat.

## A2 rubric checklist (keep it visible in the notebook)

| Criterion | Points | Covered by |
|---|---|---|
| Working code | 20 | runs top to bottom on fresh Colab; no local paths; stages commented |
| Trained baseline | 20 | BM25 fitted and tuned on train/val; TF-IDF+LogReg trained on train; evaluated on unseen test; config + training parameters printed |
| ≥ 2 metrics, explained | 15 | nDCG@10, Recall@10, MRR@10 (+ ROC-AUC/F1 for the classifier): what each shows and why it fits |
| First results | 15 | table + charts; what works, where it fails, is it acceptable, what to improve |
| Model selection rationale | 15 | why BM25 / TF-IDF+LogReg given the data; alternatives and why not yet |
| Presentation | 10 | 5–7 slides |
| Research conclusion | 5 | what the experiment showed, limitations, next experiment |

## Part A: Evaluation data

1. **Gold queries** (`source: gold`).
   - Draft ≥ 200 candidate questions written as three personas would ask them (lawyer, accountant, entrepreneur), plus citizens. Mix plain-language and terminology. At least a third must be in Kazakh.
   - Include the three TOR examples:
     - «Ответственность работодателя за задержку зарплаты»
     - «Штраф за нарушение экологических норм»
     - «Основания расторжения трудового договора»
   - Include ~20 questions the Tier-1 corpus **cannot** answer.
   - The humans pick and edit 150+ of them. Ask them, and get a native speaker to check the KK questions.

2. **Pooling for labels.**
   - For each gold query, take the union of the BM25 top-20 and the zero-shot dense top-20.
   - Export `data/eval/labeling/batch_XX.csv` with these columns: query, article_id, act, article title, the first 600 chars, and an empty `relevance` column.
   - Scale: 2 = directly answers, 1 = related or partially answers, 0 = not relevant.
   - Write `data/eval/labeling/GUIDE.md` with examples of each grade.
   - Split the batches across the three people. Have 20 queries labelled twice and report agreement (Cohen's κ, weighted).
   - Merge the labels into `qrels.jsonl` and keep the 0s.

3. **Synthetic queries** (`source: synthetic`).
   - Generate 2–3 per article with a teacher LLM, using the prompt in `ml/prompts/synthetic_queries_v1.md`: one plain-language question and one in statutory terms. KK articles get KK queries.
   - Ask the human which teacher to use: an open model on a Kaggle GPU, or an API.
   - Filter:
     - deduplicate;
     - length 4–30 words;
     - no copied article numbers or titles;
     - a language check.
   - Hand-check 50 and report the error rate.

4. **Splits.**
   - Group key = `{doc_id}:{unit_key}` (language-independent).
   - Synthetic: 80/10/10 train/val/test by group.
   - Gold: 30% val / 70% test, stratified by language. Gold is **never** used for training.
   - Save `data/eval/splits.json` with the seed and sha256 hashes.
   - Add `ml/tests/test_splits.py`: no group appears in two splits, no gold query is in train, and the hashes match.
   - Note in the report that there are two test settings:
     - **gold test:** realistic; the articles may also have synthetic training queries, as they would in production;
     - **synthetic test:** the articles were never seen in training (generalisation).

## Part B: Baselines

1. **BM25** (bm25s; RU Snowball stemmer; KK lowercase tokenisation).
   - "Training" means fitting the vocabulary and IDF on the corpus, then tuning `k1` and `b` by grid search on the train + val synthetic queries.
   - Report the final numbers on the gold test and on the synthetic test, separately.
   - This is the stand-in for the customer's current keyword search.

2. **TF-IDF + Logistic Regression relevance classifier** (the learned baseline).
   - Pair features: TF-IDF cosine, BM25 score, term overlap, length features.
   - Train it on train pairs (positives + BM25 hard negatives).
   - Evaluate it on test both as a classifier (ROC-AUC, F1) and as a reranker over the BM25 top-50 (ranking metrics).

3. **Metrics with `ranx`.**
   - **nDCG@10** is primary: it uses graded relevance and is position-aware, and users read the top of the list.
   - **Recall@10/50:** did we retrieve the right article at all? The reranker and RAG depend on this.
   - **MRR@10:** how soon the first correct article appears.
   - In the report, explain why accuracy is not used for retrieval.

4. **Breakdowns and errors.**
   - Break results down by language, by query type, and answerable vs unanswerable.
   - Give 10 failure examples, each with a diagnosis: vocabulary mismatch, cross-code question, KK morphology, an article-number query, and so on.

## Deliverables

- `ml/notebooks/A2_data_and_baseline.ipynb`: Colab-ready, runs top to bottom. It shows:
  - the data description (reusing the QA report figures);
  - the model configuration and training parameters;
  - the results table and charts.
- Run folders `ml/experiments/*_bm25_*` and `*_tfidf_logreg_*`, and an updated `ml/reports/results.csv`.
- `docs/report/A2_report.md`, covering:
  - task;
  - data;
  - baseline and why: BM25 is what keyword search does today, strong on exact terms and cheap. The alternatives (dense, hybrid) are the next phases;
  - metrics and why;
  - results and interpretation;
  - research conclusion.
- `docs/presentation/A2_slides.md` (Marp, 5–7 slides): task, data, baseline, metrics, results, conclusions, next step.

## Acceptance criteria

- [ ] The notebook runs on a fresh Colab runtime without edits. A human confirms this.
- [ ] Splits are frozen with hashes, and the split tests pass.
- [ ] The gold set has ≥ 150 labelled queries (≥ 50 KK), with κ reported.
- [ ] Every number in the report can be traced to a run folder.
