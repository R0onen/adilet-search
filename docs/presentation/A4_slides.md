---
marp: true
paginate: true
title: "Assignment 4: embeddings to fine-tuning"
---

# Assignment 4: embeddings → ML model → transformer → fine-tuning

Adilet Search · query–article relevance classification

Notebook: `ml/notebooks/A4_embeddings_to_finetuning.ipynb` · report: `docs/report/A4_report.md`

---

# Task

- X: a pair (question, candidate article). y: 1 if the question was written for that article
- Candidates: the top 20 of a tuned BM25, identical for every configuration
- Same data and split as Assignment 3: 24,264 training pairs, 195 test questions
- Leakage checks in the notebook: no article in two splits, TF-IDF fitted on the corpus only, thresholds chosen on validation

---

# Four steps, one test set

| ID | Configuration | nDCG@10 | ROC-AUC | F1 |
|---|---|---|---|---|
| E0 | TF-IDF and lexical features + Logistic Regression | 0.727 | 0.923 | 0.539 |
| E1b | E5 embeddings + Logistic Regression | 0.749 | 0.909 | 0.435 |
| E1c | E5 cosine + lexical features + gradient boosting | 0.753 | 0.953 | 0.602 |
| E2 | pretrained cross-encoder, zero-shot | 0.867 | 0.959 | 0.598 |
| E3 | cross-encoder fine-tuned on all 24,264 pairs | 0.877 | **0.974** | **0.678** |
| E3b | fine-tuned on the 4,264 pairs from written questions | **0.880** | 0.973 | 0.652 |

Ceiling for nDCG@10: 0.923.

---

# Are the differences real?

Paired over the 195 test questions, nDCG@10:

| Comparison | Difference | 95% interval | p |
|---|---|---|---|
| E1c vs E0 | +0.026 | +0.013 … +0.040 | < 0.001 |
| E2 vs E1c | +0.114 | +0.079 … +0.150 | < 0.001 |
| E3 vs E2 | +0.010 | −0.008 … +0.029 | 0.30 |
| E3b vs E2 | +0.013 | +0.003 … +0.025 | 0.016 |

---

# Answers to the research questions

- **RQ1.** Embeddings alone do not reliably beat the baseline; together with lexical features they do
- **RQ2.** The pretrained transformer is the largest step: +0.114 with no training
- **RQ3.** Fine-tuning helps a little in ranking and a lot in classification; what it is trained on matters more than how much
- **RQ4.** E3b is the product's reranker: minutes to train, no extra cost at inference

---

# Error analysis (35 of 195 questions wrong at rank 1)

| Error | Count |
|---|---|
| Right article not among the 20 candidates | 15 |
| Another article of the same code ranked higher | 15 |
| Near-duplicate article in another code | 5 |
| Kazakh questions among the 35 | 18 |

The largest group is outside any reranker's reach: the product retrieves with dense and keyword search together.

---

# In the product

- Pipeline 1.0.0 serves E3b, with a checkpoint hash in the manifest
- Through the live API: right article first for 85.1% of test questions, against 83.1% for the pretrained model
- Limits: LLM-written questions, one seed, 53 of 60 sampled questions confirmed by a person
