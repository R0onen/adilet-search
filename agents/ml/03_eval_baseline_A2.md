# ML-03: Evaluation data, Assignment 2 (Data Preparation & EDA) and the midterm baseline

This phase produces three graded or project deliverables. Do them in this order, because each one feeds the next:

| Part | What | Graded as | Needs |
|---|---|---|---|
| A | Evaluation data: synthetic queries, gold queries + labels, frozen splits | (feeds B and C) | ML-01 corpus |
| B | **Assignment 2 notebook + 1–2 page report**: dataset description, research questions, quality assessment, cleaning, EDA, features/target, split | **A2 rubric (§B.0)** | ML-01 corpus + interim snapshot, Part A synthetic pairs (gold labels if ready) |
| C | **Midterm baseline**: BM25 + TF-IDF/LogReg, ≥ 2 metrics, first results, 5–7 slides | **midterm rubric (§C.0)** | Part A splits + gold labels |

**A2 is about the data, not about models.** Its rubric has no training criterion; don't spend A2 pages on BM25. The baseline lives in Part C.

If the A2 deadline comes before gold labelling is finished, build the A2 notebook on the corpus + synthetic pairs and state that clearly. Add gold statistics later as an appendix cell.

---

## Part A: Evaluation data

1. **Synthetic queries** (`source: synthetic`). Do these first; they need no humans.
   - Generate 2–3 per article with a teacher LLM, using the prompt in `ml/prompts/synthetic_queries_v1.md`:
     - one plain-language question;
     - one in statutory terms.
   - KK articles get KK queries.
   - Ask the human which teacher to use: an open model on a Kaggle GPU, or an API.
   - **Keep the unfiltered output** (`data/interim/synthetic_raw.jsonl`), because the A2 notebook shows the filtering as a cleaning step with before/after counts.
   - Filter:
     - deduplicate (exact and near-duplicate);
     - length 4–30 words;
     - no copied article numbers or titles;
     - a language check (a KK article must get a KK query).
   - Hand-check 50 and report the error rate.

2. **Gold queries** (`source: gold`).
   - Draft ≥ 200 candidate questions written as three personas would ask them (lawyer, accountant, entrepreneur), plus citizens. Mix plain-language and terminology. At least a third must be in Kazakh.
   - Include the three TOR examples:
     - «Ответственность работодателя за задержку зарплаты»
     - «Штраф за нарушение экологических норм»
     - «Основания расторжения трудового договора»
   - Include ~20 questions the Tier-1 corpus **cannot** answer.
   - The humans pick and edit 150+ of them. Ask them, and get a native speaker to check the KK questions.

3. **Pooling for labels.**
   - For each gold query, take the union of the BM25 top-20 and the zero-shot dense top-20.
   - Export `data/eval/labeling/batch_XX.csv` with these columns: query, article_id, act, article title, the first 600 chars, and an empty `relevance` column.
   - Scale: 2 = directly answers, 1 = related or partially answers, 0 = not relevant.
   - Write `data/eval/labeling/GUIDE.md` with examples of each grade.
   - Split the batches across the three people. Have 20 queries labelled twice and report agreement (weighted Cohen's κ).
   - Merge the labels into `qrels.jsonl` and keep the 0s.

4. **Splits.**
   - Group key = `{doc_id}:{unit_key}` (language-independent).
   - Synthetic: 80/10/10 train/val/test by group, stratified by act (so every code appears in every split).
   - Gold: 30% val / 70% test, stratified by language. Gold is **never** used for training.
   - Save `data/eval/splits.json` with the seed and sha256 hashes.
   - Add `ml/tests/test_splits.py`: no group appears in two splits, no gold query is in train, and the hashes match.
   - Note in the reports that there are two test settings:
     - **gold test:** realistic; the articles may also have synthetic training queries, as they would in production;
     - **synthetic test:** the articles were never seen in training (generalisation).

---

## Part B: Assignment 2: Data Preparation & EDA

### B.0 Rubric checklist (keep this table in the notebook's first markdown cell, each row linked to its section)

| # | Criterion | Pts | Where it is covered |
|---|---|---|---|
| 1 | Dataset selection and description | 8 | §1 of the notebook: source (adilet.zan.kz, Ministry of Justice of RK), domain, origin, collection period, purpose, why it fits, links |
| 2 | Research problem formulation | 10 | §2: problem, goal, 3 RQs, hypotheses |
| 3 | Loading and reproducibility | 5 | §0: Restart → Run All on a fresh Colab, data downloaded by script, no local paths |
| 4 | Data structure examination | 7 | §3: shape, dtypes, columns, `info()`, `describe()`, a data dictionary explaining each column |
| 5 | Data quality assessment | 10 | §4: a quantified table (count and % per issue) |
| 6 | Data cleaning | 10 | §5: every step justified, before/after table |
| 7 | EDA | 15 | §6: ≥ 5 numbered analytical observations |
| 8 | Visualization | 10 | §6: ≥ 5 charts with title, axis labels, legend, interpretation |
| 9 | Features and target | 8 | §7: X and y, why this target, the effect of each feature, a leakage check |
| 10 | Train/validation/test split | 7 | §8: group split, proportions justified, stratification, the "not temporal" argument |
| 11 | Scientific interpretation | 5 | §9: findings mapped to the RQs |
| 12 | Brief research report | 5 | `docs/report/A2_report.md`, 1–2 pages |

### B.1 What "the dataset" is (decide and state it in §1)

The A2 dataset has two linked tables:

1. **The legislative corpus**: the article-level rows from ML-01 (`articles.parquet` / `chunks.parquet`). They are scraped from the official open portal **adilet.zan.kz** (Reference Control Bank of Regulatory Legal Acts of the Republic of Kazakhstan). Use the Tier-1 codes in RU and KK, as of the scrape date.
2. **The query–article relevance pairs**: synthetic (+ gold, when labelled) queries joined with their articles. Add negatives too: BM25-mined articles that are not the source, at a fixed ratio such as 1:4.

The supervised task this dataset prepares for is **graded or binary relevance of a (query, article) pair**. That is exactly the reranking stage of the product (see D-010).

For §1, give the following:
- **Source:** adilet.zan.kz, with links to each code's page.
- **Domain:** Kazakhstan legislation.
- **Origin:** official texts published by the Institute of Legislation and Legal Information of the RK; queries are synthetic (LLM) and team-written.
- **Collection period:** the `scraped_at` range and the revision-date range of the acts.
- **Purpose:** training and evaluating semantic search.
- **Why it fits:** the authoritative texts, both languages, and article granularity, which matches what users need.

### B.2 Research questions (§2)

**Problem:** keyword search over statutes fails when the user's wording differs from the statute's wording. **Goal:** characterise the corpus and the query–article relation, so we can choose the retrieval design and the model inputs.

Use these three RQs, or improve them. Write each hypothesis **before** measuring, and state the measured result in §9 even if the hypothesis is rejected.

- **RQ1 (vocabulary gap).** How much lexical overlap is there between plain-language queries and the articles that answer them, compared with terminology queries?
  - *H1:* plain-language queries share markedly fewer lemmas with their relevant article than terminology queries do (compare the median Jaccard of the two groups), so keyword matching alone is insufficient.
- **RQ2 (length vs model context).** How are article lengths distributed per code and language, and what share exceeds a 512-token encoder context?
  - *H2:* a non-trivial share of articles (concentrated in a few codes, e.g. Tax and Administrative) exceeds 512 tokens, which justifies chunking.
- **RQ3 (RU vs KK parity).** Are the Kazakh and Russian versions equally complete and comparable (coverage, parallel alignment, length ratio)?
  - *H3:* KK coverage and alignment are lower than RU, and KK texts tokenise into more tokens, so KK needs separate evaluation.

### B.3 Notebook sections

**§0 Setup and loading.**
- Detect Colab/Kaggle/local.
- Clone the repo and install `ml/requirements-colab.txt`.
- Download the data with `ml/scripts/download_data.py --corpus-version X`.
- **The grader must be able to run it without our tokens.** Publish the A2 data (the corpus snapshot is public law, plus the synthetic pairs) as a **public** HF dataset or GitHub release asset. Ask the human to confirm making it public. If they refuse, commit a compressed subset that is large enough for every analysis.
- Seed everything and print the library versions.

**§3 Structure.**
- `shape`, `dtypes`, column names, `info()`, `describe(include="all")` for both tables.
- A **data dictionary** table: column, type, meaning, example, and why it matters for search.
- Explain each significant column in one sentence: unit_type, unit_status, doc_type, doc_status, revision_date, amendment_notes, parallel_article_id, token_len, query_type, relevance.

**§4 Quality assessment.** Every row is quantified (count, %, per act/language where it matters), not just the output of a function call. Work from the **pre-cleaning snapshot** in `data/interim/` (ML-01 keeps it).

| Issue | What to measure |
|---|---|
| Missing values | per column. Separate structurally-null fields (e.g. `unit_title` for points) from true gaps |
| Duplicates | exact `text` duplicates, and boilerplate such as «Статья исключена…»; near-duplicates (MinHash or cosine > 0.95); duplicate synthetic queries |
| Incorrect values | empty or very short texts; parse junk (navigation, HTML entities, «Сноска» left inside `text`); future dates; revision earlier than adoption |
| Outliers | length outliers by IQR/z-score per code (huge annex tables, one-line articles); list examples |
| Inconsistent categories | status strings, doc_type spelling, RU vs KK labels for the same category, unit numbering formats (`113-1` vs `113.1`) |
| Wrong types | dates stored as strings, numbers as text; mixed-script characters (Latin homoglyphs inside Cyrillic words), NBSP and other whitespace |
| Structural integrity | gaps in article numbering per code (each explained), RU↔KK unmatched articles, `chunk_count` consistency |

**§5 Cleaning.**
- One subsection per step. Each one gives: the problem (a number from §4), the action, the **justification**, and the rows/values affected.
- End with a before → after table: rows, columns, nulls, duplicates, mean and max length.
- The legal-text rule (CLAUDE.md) applies:
  - `text` stays verbatim apart from whitespace/NFC normalisation and the removal of navigation junk and footnotes (which move to `amendment_notes`);
  - homoglyph fixes or lower-casing go into derived fields only (e.g. a normalised search field), and the notebook says so;
  - excluded articles are **kept and flagged**, not dropped: users must see that a provision was excluded. Explain this, because a bare `dropna()`/`drop_duplicates()` loses points.

**§6 EDA + visualisations.**
- At least 5 numbered observations, each one a finding with a number and its consequence for the system. A shape description alone doesn't count.
- At least 5 charts, each with a title, axis labels, a legend or annotations, and 1–3 sentences of interpretation directly under it.

Suggested charts (choose the ones that carry a finding):
1. Articles per code × language (grouped bar). This shows coverage, which feeds RQ3.
2. Article length distribution in tokens, per code (box or violin, log scale), with lines at 400 and 512 tokens. This answers RQ2.
3. The RU vs KK token length of parallel articles (scatter with a y = x line + ratio histogram). This feeds RQ3.
4. Query–article lemma overlap (Jaccard) for **positive vs negative** pairs, split by query type (box plot). This is the feature↔target relation, for RQ1.
5. The relevance label distribution and class imbalance (bar), per split.
6. Amendment intensity per code (share of articles with amendment notes) and revision dates (timeline). This shows how "alive" each code is, and the risk of serving stale law.
7. Top distinctive terms per code (TF-IDF). This hints at the vocabulary the queries need to reach.

**§7 Features and target.**
- **y:** the relevance of the pair. Binary `relevant = relevance ≥ 1` for the main task; graded 0/1/2 kept for ranking metrics. Explain why: it is what the product decides at the reranking step.
- **X:** query text, article `text_for_embedding`, and engineered pair features:
  - lemma overlap / Jaccard, BM25 score, TF-IDF cosine;
  - query and article length;
  - language;
  - doc_type, unit_status, has_amendments;
  - query_type.
- For each feature, state its expected effect on y, and back it with a chart or correlation where possible.
- **Leakage check** (each one in writing, with the code that verifies it):
  - synthetic queries generated from the article itself copy its words, so overlap features are inflated for synthetic positives; quantify this against gold pairs;
  - RU and KK versions of one article must stay in the same split (group key);
  - negatives for train are mined from train articles only;
  - the TF-IDF/BM25 statistics used as features are fit on train only;
  - no feature uses `qrels`, the article id or the article title copied into the query.

**§8 Split.**
- Load `data/eval/splits.json` (Part A); don't re-split in the notebook.
- Show the group sizes, the per-split counts by language, act and label, and the class ratio per split.
- **Justify** 80/10/10: the number of groups, enough val queries for stable metrics, and a test set big enough for per-language breakdowns.
- **Why grouping:** it prevents leakage across language versions.
- **Why stratifying by act:** every code must be present in every split.
- **Why a random group split is acceptable here:** the data is a single snapshot of the corpus, not a time series. Name the stricter alternative (a split by code, to test transfer to unseen domains) as future work.

**§9 Interpretation.**
- Answer RQ1–RQ3 with the measured numbers, and accept or reject each hypothesis.
- Then say what this means for the system:
  - the chunk size;
  - the need for hybrid retrieval;
  - separate KK evaluation;
  - the in-force filter;
  - which features enter the A4 classical model.

### B.4 Deliverables

- `ml/notebooks/A2_data_preparation_eda.ipynb`: thin, calls `adilet_ml`. Runs with Restart → Run All on a fresh Colab with no edits. Saves its figures to `ml/reports/figures/a2_*.png`.
- **`docs/report/A2_report.md`**, 1–2 pages in academic style:
  - problem → data → method → main results (with 2–3 figures or numbers) → limitations → conclusions;
  - references in numbered form, including adilet.zan.kz, the tools used, and the methods cited (e.g. BM25 / Robertson & Zaragoza; the multilingual E5 paper for the tokenizer).
- Export the report to PDF if the course requires a file:
  ```bash
  npx md-to-pdf docs/report/A2_report.md
  ```

### B.5 Acceptance criteria

- [ ] A human ran Restart → Run All on a fresh Colab **without logging in to anything**, and it passed.
- [ ] Every rubric row in §B.0 points to a section that exists. There are ≥ 5 observations and ≥ 5 interpreted charts.
- [ ] The quality table is quantified, and every cleaning step has a justification and a before/after.
- [ ] The leakage checks run as code and pass.
- [ ] The report is ≤ 2 pages, with references.

---

## Part C: Midterm: baseline model

### C.0 Midterm rubric checklist

| Criterion | Points | Covered by |
|---|---|---|
| Working code | 20 | runs top to bottom on fresh Colab; no local paths; stages commented |
| Trained baseline | 20 | BM25 fitted and tuned on train/val; TF-IDF+LogReg trained on train; evaluated on unseen test; config + training parameters printed |
| ≥ 2 metrics, explained | 15 | nDCG@10, Recall@10, MRR@10 (+ ROC-AUC/F1 for the classifier): what each shows and why it fits |
| First results | 15 | table + charts; what works, where it fails, is it acceptable, what to improve |
| Model selection rationale | 15 | why BM25 / TF-IDF+LogReg given the data (link to A2 findings); alternatives and why not yet |
| Presentation & defence | 10 | 5–7 slides (task, data, baseline, metrics, results, conclusions, next step); the presenter can explain the code and answer questions (`docs/presentation/qa_midterm.md`) |
| Research conclusion | 5 | what the experiment showed, limitations, next experiment |

### C.1 Baselines

1. **BM25** (bm25s; RU Snowball stemmer; KK lowercase tokenisation).
   - "Training" means fitting the vocabulary and IDF on the corpus, then tuning `k1` and `b` by grid search on the train + val synthetic queries.
   - Report the final numbers on the gold test and on the synthetic test, separately.
   - This is the stand-in for the customer's current keyword search.
2. **TF-IDF + Logistic Regression relevance classifier** (the learned baseline).
   - Use the pair features defined in A2 §7.
   - Train it on train pairs (positives + BM25 hard negatives).
   - Evaluate it on test both as a classifier (ROC-AUC, F1) and as a reranker over the BM25 top-50 (ranking metrics).
3. **Metrics with `ranx`.**
   - **nDCG@10** is primary: it uses graded relevance and is position-aware, and users read the top of the list.
   - **Recall@10/50:** did we retrieve the right article at all? The reranker and RAG depend on this.
   - **MRR@10:** how soon the first correct article appears.
   - Explain why accuracy is not used for retrieval.
4. **Breakdowns and errors.**
   - Break results down by language, by query type, and answerable vs unanswerable.
   - Give 10 failure examples, each with a diagnosis: vocabulary mismatch (which links back to A2 RQ1), cross-code question, KK morphology, an article-number query, and so on.

### C.2 Deliverables

- `ml/notebooks/midterm_baseline.ipynb`: Colab-ready; prints the model configuration and training parameters; shows the results table and charts.
- Run folders `ml/experiments/*_bm25_*` and `*_tfidf_logreg_*`, and an updated `ml/reports/results.csv`.
- `docs/report/midterm_report.md`, covering:
  - task;
  - data (short; link to A2);
  - baseline and why;
  - metrics and why;
  - results and interpretation;
  - research conclusion.
- `docs/presentation/midterm_slides.md` (Marp, 5–7 slides): task, data, baseline, metrics, results, conclusions, next step.
- `docs/presentation/qa_midterm.md`: a walk-through of the notebook cell by cell (what each stage does and why), plus 10 likely questions with short answers (why BM25, why nDCG, how the split avoids leakage, what k1/b do, why LogReg, what fails and why). The presenter must be able to defend the code.

### C.3 Acceptance criteria

- [ ] The notebook runs on a fresh Colab runtime without edits. A human confirms this.
- [ ] Splits are frozen with hashes, and the split tests pass.
- [ ] The gold set has ≥ 150 labelled queries (≥ 50 KK), with κ reported. If labelling is late, the synthetic-test numbers come first, clearly labelled as synthetic.
- [ ] Every number in the report can be traced to a run folder.
