---
marp: true
title: A4 Embeddings to Fine-Tuning
---

> **Superseded (2026-11-11).** The numbers in this draft came from a 10-query toy set on a paraphrased sample. That set and its runs were removed. Current results are in `ml/reports/results.csv`; this document is rewritten in the A3/A4 phases.

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
