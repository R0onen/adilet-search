---
marp: true
title: A4 Embeddings to Fine-Tuning
---

# A4: Relevance Classification

Task: classify query-article pairs for reranking.

---

# Local Classifier

`20261008_tfidf_logreg_seed`

| Metric | Value |
|---|---:|
| ROC-AUC | 0.9072 |
| F1 | 0.4898 |
| PR-AUC | 0.7118 |
| nDCG@10 | 0.8198 |

---

# Research Questions

- Dense hash path does not beat BM25 on seed nDCG@10
- TF-IDF/logistic retrieves positives but ranks below BM25
- Transformer and fine-tuned transformer remain GPU/model-download work

---

# Next Experiment

Run E1/E2/E3 on the same split after gold labels and checkpoints exist, then compare quality gain
against CPU latency.

<!-- source: docs/report/A4_report.md -->
