# Assignment status (15 November 2026)

| Assignment | State | Where |
|---|---|---|
| A2 and midterm: data and baseline | submitted earlier; summary of the data and the baseline | `docs/report/A2_report.md`, `ml/reports/data_quality.md`, `ml/reports/results.csv` |
| A3: training and fine-tuning | done; notebook executed on a GPU with outputs | `ml/notebooks/A3_training_finetuning.ipynb`, `docs/report/A3_report.md` |
| A4: embeddings → ML model → transformer → fine-tuning | done; notebook executed with outputs, significance tests and error analysis | `ml/notebooks/A4_embeddings_to_finetuning.ipynb`, `docs/report/A4_report.md` |
| Final model | pipeline 1.0.0 with the reranker fine-tuned in A4 | `ml/MODEL_CARD.md`, `ml/experiments/final-selection/` |
| Final evaluation | through the live API, with a human-checked subset | `docs/report/final_eval.md` |
| Load test | 10 users on the deployed corpus | `docs/report/load_test.md` |

What a person did: reviewed 60 of the 195 test questions (`data/eval/labeling/synthetic_review.csv`: 53 correct, 3 wrong, 4 too vague).

Not done: a gold set written by lawyers. All quality numbers are on LLM-written questions and say so where they are quoted.
