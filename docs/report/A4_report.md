# Assignment 4: Embeddings → ML model → Transformer → Fine-tuning

Notebook with outputs: `ml/notebooks/A4_embeddings_to_finetuning.ipynb` (executed 15 November 2026 on an RTX 4060 Laptop GPU, seed 42, 12.5 minutes). Raw results: `results.csv`, `significance.csv`, `breakdown.csv`, `errors.csv` and `config.json` written by the notebook.

## Task

Query–article relevance classification, used as the re-ranking stage of the legal search system.

- **X:** a pair (question, candidate article). **y:** 1 if the question was written for that article.
- **Candidates:** the top 20 articles of a tuned BM25, identical for every configuration.
- **Data and split:** as in Assignment 3 (8 codes, Russian and Kazakh; 24,264 training pairs, 2,380 validation, 3,900 test pairs from 195 questions; split by article). Class balance on test: 1 positive per 21 negatives, handled with class weights and a threshold chosen on validation.
- **Leakage checks:** asserted in the notebook that no article is in two splits; TF-IDF is fitted on the corpus, not on questions; thresholds and hyperparameters use train and validation only; training negatives come from training questions only.

## Configurations and results (test set)

| ID | Representation and model | nDCG@10 | MRR@10 | ROC-AUC | PR-AUC | F1 | Training |
|---|---|---|---|---|---|---|---|
| E0 | TF-IDF and lexical features + Logistic Regression | 0.727 | 0.667 | 0.923 | 0.510 | 0.539 | seconds |
| E1a | `multilingual-e5-base` cosine similarity, no training | 0.753 | 0.706 | 0.855 | 0.321 | 0.355 | – |
| E1b | e5 embeddings (`|u−v|`, `u⊙v`, cosine; 1,537 features) + Logistic Regression | 0.749 | 0.703 | 0.909 | 0.439 | 0.435 | 7 s |
| E1c | e5 cosine + lexical features + gradient boosting | 0.753 | 0.699 | 0.953 | 0.588 | 0.602 | 55 s |
| E2 | pretrained multilingual cross-encoder, zero-shot | 0.867 | 0.849 | 0.959 | 0.636 | 0.598 | – |
| E3 | the same cross-encoder, fine-tuned on all 24,264 pairs | 0.877 | 0.862 | **0.974** | **0.763** | **0.678** | 5.4 min |
| E3b | fine-tuned on the 4,264 pairs from written questions only | **0.880** | **0.866** | 0.973 | 0.719 | 0.652 | 2.2 min |

Ceiling for nDCG@10 and MRR@10: 0.923 (the correct article is among the candidates for 92.3% of the questions). Embedding dimension: 768. Selected hyperparameters: E1b `C = 0.001`; E1c learning rate 0.05, 400 iterations, 15 leaves, 50 samples per leaf, L2 1.0 (randomised search, 20 trials, GroupKFold); E3 and E3b learning rate 1e-5 (chosen in Assignment 3), batch 32, binary cross-entropy, AdamW, best epoch by validation nDCG@10.

## Significance (paired over the 195 test questions, nDCG@10)

| Comparison | Mean difference | 95% bootstrap interval | p (randomisation) | Better / worse |
|---|---|---|---|---|
| E1b vs E0 | +0.022 | −0.024 … +0.068 | 0.35 | 50 / 44 |
| E1c vs E0 | +0.026 | +0.013 … +0.040 | < 0.001 | 34 / 8 |
| E2 vs E1c | +0.114 | +0.079 … +0.150 | < 0.001 | 62 / 12 |
| E3 vs E2 | +0.010 | −0.008 … +0.029 | 0.30 | 16 / 9 |
| E3b vs E2 | +0.013 | +0.003 … +0.025 | 0.016 | 13 / 3 |
| E3b vs E3 | +0.003 | −0.013 … +0.019 | 0.69 | 10 / 10 |
| E3 vs E0 | +0.150 | +0.110 … +0.191 | < 0.001 | 69 / 10 |

## Answers to the research questions

- **RQ1. Do dense embeddings beat the baseline representation?** Only partly. Embedding features alone rank slightly better than the baseline (0.749 against 0.727) but the difference is not significant and the classifier is worse (ROC-AUC 0.909 against 0.923). Adding the embedding cosine to the lexical features is significantly better than the baseline on both counts (nDCG@10 +0.026, ROC-AUC 0.953). The embedding model is weak in Kazakh (0.642 nDCG@10 against 0.822 in Russian).
- **RQ2. How much better is a pretrained transformer than classical ML on embeddings?** Much: +0.114 nDCG@10 with no training (p < 0.001). A model that reads the question and the article together beats any model that compares two separately computed vectors.
- **RQ3. How much does fine-tuning help?** Statistically: fine-tuning on all pairs is not significantly better at ranking than zero-shot (+0.010, p = 0.30); fine-tuning on the written questions only is (+0.013, p = 0.016). Practically: the ranking gain is small, the classification gain is large (PR-AUC 0.636 → 0.763, F1 0.598 → 0.678). The written-questions model is as good with a sixth of the data, so article titles add little as training questions.
- **RQ4. Cost and the choice for the product.** E0 and E1 score 20 candidates in under a millisecond but stop at 0.75 nDCG@10. The cross-encoder needs 32–38 ms per 20 candidates on the GPU and about one second on the product's CPU, so the product reranks 5 candidates. Fine-tuning costs minutes once and nothing at inference. **E3b is the product's reranker** (pipeline 1.0.0): through the live API it ranks the right article first for 85.1% of the test questions with 5 candidates, against 83.1% for the pretrained model (`ml/experiments/final-selection/`).

## Error analysis (E3)

E3 does not put the correct article first for 35 of the 195 test questions (17.9%). E1c was right on 11 of them; E3 is right on 61 questions that E1c got wrong.

| Error type | Count | Example | Likely cause | Possible fix |
|---|---|---|---|---|
| Correct article not among the 20 candidates | 15 | "Кто может действовать от имени другого человека в Казахстане?": the article "Законный представитель физического лица" is not retrieved | BM25 needs shared words | dense retrieval for candidates (the product fuses dense and BM25) |
| Another article of the same code above the correct one | 15 (correct one at rank 2–3 in 10, 4–5 in 5) | a question about the size of a fine for an environmental violation: a specific violation article above the general article "Административный штраф" | general and special articles both answer; one label per question | several relevant articles per question |
| Near-duplicate article in another code | 5 | "Условия и компенсации при командировке": Tax Code "Вычет сумм компенсаций при командировках" above the Labor Code article | the subject is regulated in two codes | a filter by code; multi-label evaluation |
| Kazakh wording | 18 of the 35 (41% of the test questions are Kazakh) | "Регресс талап ету": "Зиян келтiрген тұлғаға керi талап қою құқығы" above "Регрестік талаптар" | the base model was not trained on Kazakh | Kazakh training questions |
| Question that does not match its label | 1 found in the human review | "Если предприятие меняет владельца…" for an article about "учреждение" | generation error | human review flags |

The Kazakh row overlaps the others. The largest group is outside any reranker's reach.

## Follow-up: training on all 40 acts

After the corpus was extended to 40 acts, E3b was repeated with 527 more training questions about the 32 added acts (`ml/scripts/train_reranker.py`, `ml/experiments/reranker-40acts/`). On the 195 test questions nDCG@10 went from 0.880 to 0.885 (p = 0.40); on 55 everyday questions about the added acts from 0.535 to 0.524 (p = 0.56). Neither change is significant, and through the live hybrid search the everyday result is identical (58% first), so E3b stays the product's reranker. The weak results on the added acts come from retrieval (the article is among the 20 BM25 candidates for 65% of those questions) and from wording, not from what the reranker was trained on.

## Limits

- LLM-written questions with one labelled article; 53 of 60 sampled test questions confirmed by a person.
- One seed; bootstrap intervals stand in for repeated runs.
- A data bug found after these runs: 22 question ids of the training split were used twice in `data/eval/synthetic/` (the generator counted lines instead of continuing after the highest id when it resumed). When questions and labels were joined on the id, 44 training questions were also paired with the other question's article. Validation and test were not affected, so the test numbers stand; the training data had about 5% noisy questions. The ids are fixed in the repository and the generator no longer reuses ids; the notebooks were not re-run.
- Inference times are on a GPU; the product's reranker runs on a CPU.

## Reproduce

Open the notebook on a GPU runtime and run all cells. No tokens are needed.
