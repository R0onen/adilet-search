---
marp: true
paginate: true
title: "Assignment 3: training and fine-tuning"
---

# Assignment 3: training and fine-tuning

Adilet Search · reranking articles of Kazakhstan legislation

Notebook: `ml/notebooks/A3_training_finetuning.ipynb` · report: `docs/report/A3_report.md`

---

# Task and data

- Input: a question and a candidate article. Output: does the article answer the question?
- Used as the reranker: BM25 proposes 20 articles, the model reorders them
- 8 codes, Russian and Kazakh, 9,259 articles
- 803 LLM-written questions for 400 articles, split by article 70 / 15 / 15
- 24,264 training pairs · 195 test questions (3,900 pairs, 4.6% positive)
- Ceiling: the right article is among the 20 candidates for 92.3% of test questions

---

# Models compared on one split

| Model | Family | nDCG@10 | F1 | ROC-AUC | Training |
|---|---|---|---|---|---|
| BM25, tuned | classical | 0.697 | – | – | – |
| TF-IDF features + LogReg, tuned | classical | 0.727 | 0.536 | 0.923 | seconds |
| TF-IDF features + Linear SVM, tuned | classical | 0.726 | 0.535 | 0.923 | seconds |
| Cross-encoder, zero-shot | transfer | 0.867 | 0.598 | 0.959 | – |
| Cross-encoder, frozen encoder + head | transfer | **0.871** | 0.600 | 0.962 | 2.6 min |
| Cross-encoder, fully fine-tuned | fine-tuning | 0.867 | **0.693** | **0.974** | 5.7 min |
| Qwen2.5-0.5B + LoRA | LoRA | 0.805 | 0.595 | 0.951 | 37 min |

---

# Hyperparameter tuning

| Model | Search | Selected | Effect on test |
|---|---|---|---|
| BM25 | k1 × b grid, per language | ru: 1.2 / 0.9 · kk: 2.0 / 0.9 | 0.702 → 0.697 |
| LogReg | C × class weight, GroupKFold | C 0.1, balanced | 0.724 → 0.727 |
| Linear SVM | C × class weight | C 0.01, balanced | 0.726 |
| Cross-encoder | learning rate 1e-5, 2e-5, 5e-5 | 1e-5 | best on validation |

Tuning the classical models did not help: with eight lexical features they are limited by their inputs.

---

# What we learned

1. Transfer learning is the decisive step: +0.14 nDCG@10 with no training
2. Full fine-tuning improves the classifier (F1 0.60 → 0.69), not the ranking, on this training set
3. Training only the head gives the best ranking with 0.1% of the parameters
4. LoRA on a small general LLM is below the cross-encoder and 7 times slower
5. Kazakh is weaker for every model (cross-encoder 0.82 against 0.90 in Russian)

---

# Limits and next step

- LLM-written questions, one labelled article each; a person confirmed 53 of 60 sampled
- One seed; differences under 0.02 are within noise
- 84% of the training questions are article titles → Assignment 4 trains on the written questions only
