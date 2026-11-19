# Assignment 3: Model training and fine-tuning

Notebook with outputs: `ml/notebooks/A3_training_finetuning.ipynb` (executed 15 November 2026 on an RTX 4060 Laptop GPU, seed 42, 62 minutes). Raw results: `results.csv`, `breakdown.csv` and `config.json` written by the notebook.

## Task and data

For a user's question and an article of Kazakhstan legislation, decide whether the article answers the question. The search system uses this model as its **reranker**: BM25 proposes 20 candidate articles and the model reorders them. Every model is therefore scored as a classifier of (question, article) pairs and as a ranker.

- **Corpus:** AdiletCodex v1.0, the 8 main codes in Russian and Kazakh, 9,259 articles.
- **Questions:** 803 LLM-written questions for 400 sampled articles (one in everyday wording, one in legal terminology per article), plus article titles used only for training. Split by article (70 / 15 / 15, seed 42), so no article is in two subsets.
- **Pairs:** 24,264 training pairs (the correct article plus 7 wrong candidates drawn at random from the 20), 2,380 validation pairs, 3,900 test pairs from 195 test questions (4.6% positive).
- **Ceiling:** the correct article is among the 20 candidates for 92.3% of the test questions; no reranker can do better.
- **Labels are automatic:** the article a question was written for is the only relevant one. A person checked 60 sampled test questions: 53 correct, 3 wrong, 4 too vague.

## Results (test set)

| Model | Family | nDCG@10 | MRR@10 | F1 | ROC-AUC | Trainable parameters | Training |
|---|---|---|---|---|---|---|---|
| BM25, default (k1 1.2, b 0.75) | classical | 0.702 | 0.654 | – | – | – | – |
| BM25, tuned | classical | 0.697 | 0.648 | – | – | – | – |
| TF-IDF features + LogReg, baseline | classical | 0.724 | 0.664 | 0.554 | 0.923 | 9 | seconds |
| TF-IDF features + LogReg, tuned | classical | 0.727 | 0.667 | 0.536 | 0.923 | 9 | seconds |
| TF-IDF features + Linear SVM, tuned | classical | 0.726 | 0.666 | 0.535 | 0.923 | 9 | seconds |
| Cross-encoder, zero-shot | transfer | 0.867 | 0.849 | 0.598 | 0.959 | 0 | – |
| Cross-encoder, frozen encoder + trained head | transfer | **0.871** | 0.854 | 0.600 | 0.962 | 148 thousand | 2.6 min |
| Cross-encoder, fully fine-tuned | fine-tuning | 0.867 | 0.849 | **0.693** | **0.974** | 118 million | 5.7 min |
| Qwen2.5-0.5B + LoRA | LoRA | 0.805 | 0.771 | 0.595 | 0.951 | 542 thousand (0.11%) | 37.1 min |

nDCG@10 by language and question type:

| Model | Kazakh | Russian | Plain | Terminology |
|---|---|---|---|---|
| BM25, tuned | 0.646 | 0.732 | 0.665 | 0.731 |
| TF-IDF features + LogReg, tuned | 0.689 | 0.752 | 0.703 | 0.752 |
| Cross-encoder, zero-shot | 0.821 | 0.899 | 0.848 | 0.888 |
| Cross-encoder, fully fine-tuned | 0.826 | 0.895 | 0.832 | 0.904 |
| Qwen2.5-0.5B + LoRA | 0.725 | 0.859 | 0.788 | 0.823 |

## Hyperparameter tuning

| Model | Search space | Selected on validation | Effect on test |
|---|---|---|---|
| BM25 | k1 ∈ {0.6, 0.9, 1.2, 1.5, 2.0} × b ∈ {0.3, 0.5, 0.75, 0.9}, per language | ru: k1 1.2, b 0.9; kk: k1 2.0, b 0.9 | 0.702 → 0.697 nDCG@10: no gain |
| Logistic Regression | C ∈ {0.01, 0.1, 1, 10, 100} × class weight ∈ {none, balanced}, GroupKFold | C 0.1, balanced | 0.724 → 0.727: within noise |
| Linear SVM | C ∈ {0.01, 0.1, 1, 10} × class weight | C 0.01, balanced | 0.726 |
| Cross-encoder fine-tuning | learning rate ∈ {1e-5, 2e-5, 5e-5} | 1e-5 (validation nDCG@10 0.864 / 0.854 / 0.857) | – |

Fine-tuning settings: binary cross-entropy on one logit, AdamW (weight decay 0.01, 10% warm-up), batch 32, 2 epochs, 320 tokens. LoRA: r 8, alpha 16, dropout 0.05 on `q_proj` and `v_proj`, learning rate 2e-4, effective batch 16, 2 epochs, class-weighted cross-entropy.

## What the results say

1. **Transfer learning is the decisive step.** A cross-encoder pretrained on multilingual passage ranking adds +0.14 nDCG@10 over the best classical model without seeing one of our pairs. It transfers to Kazakh (0.821 against 0.646 for BM25), a language it was not trained on, though less well than to Russian.
2. **Tuning the classical models did not pay off.** The selected BM25 and LogReg parameters are no better on the test set than the defaults. With eight lexical features the models are limited by their inputs.
3. **Full fine-tuning improves the classifier, not the ranking, on this training set.** F1 rises from 0.60 to 0.69 and ROC-AUC from 0.959 to 0.974, while nDCG@10 stays at 0.867. Training only the head gives the best ranking of this notebook (0.871) with 0.1% of the parameters. Fine-tuning made plain-language questions slightly worse (0.848 → 0.832) and terminology questions better (0.888 → 0.904): 84% of the training questions are article titles. Assignment 4 follows this up.
4. **LoRA on a small general LLM is not competitive here:** below the cross-encoder on every metric, weakest in Kazakh, and seven times slower to train.

## Limits

- LLM-written questions, one labelled article each, 195 test questions: differences below about 0.02 nDCG@10 are within noise.
- One seed.
- A data bug found after these runs: 22 question ids of the training split were used twice in `data/eval/synthetic/` (the generator counted lines instead of continuing after the highest id when it resumed). When questions and labels were joined on the id, 44 training questions were also paired with the other question's article. Validation and test were not affected, so the test numbers stand; the training data had about 5% noisy questions. The ids are fixed in the repository and the generator no longer reuses ids; the notebooks were not re-run.
- An earlier version of this experiment kept the 7 highest-ranked wrong candidates as negatives. That made "low BM25 rank" a sure sign of a positive in training and broke the feature-based models; the negatives are now drawn at random from the candidates. Numbers from that earlier version are not used anywhere.

## Reproduce

Open the notebook on a GPU runtime and run all cells. It clones the repository, downloads and verifies the corpus, and needs no tokens. On a GPU with less than 12 GB the LoRA step uses gradient accumulation (2 × 8) instead of a batch of 16.
