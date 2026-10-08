# ML-05: Embeddings → ML model → Transformer → Fine-tuning (Assignment 4), week 5, first half

**Goal:** answer RQ1–RQ4 with four configurations of one task, and produce the **production reranker** as a by-product.

## Task framing (put this in the report, see D-010)

The task is **query–article relevance classification**, used as the re-ranking stage of search.

- **X:** a pair (query, candidate article chunk).
- **y:** 1 if the article is relevant (qrels ≥ 1), otherwise 0.
- **Candidates:** the first-stage top-50 from the fixed hybrid retriever of ML-04. They are identical for every configuration, so classification metrics and ranking metrics are measured on the same candidates.
- **Class imbalance is real** (~1–3 positives per 50). Report the ratio and handle it with class weights and threshold tuning on val.

**Splits** are the same as in ML-03:
- train = synthetic train;
- val = synthetic val + gold val;
- test = gold test and synthetic test, reported separately.

**Leakage checks:**
- no group appears in two splits;
- hard negatives for train are mined only from train-split queries;
- the TF-IDF vocabulary and any scalers are fit on train only.

## Configurations

| ID | Representation | Model | Notes |
|---|---|---|---|
| E0 baseline | TF-IDF (word 1–2-grams + char 3–5-grams) pair features | Logistic Regression | from ML-03; the "baseline representation" for RQ1 |
| E1 embeddings → ML | dense embeddings from the best encoder in ML-04 (state the dimension); features `[u, v, |u−v|, u⊙v, cos(u,v), bm25]` | LogReg and LightGBM/XGBoost, tuned with Optuna (≥ 30 trials, GroupKFold) | optional second embedding: FastText trained on the corpus, to show static vs contextual |
| E2 transformer, no fine-tuning | the model's own tokenizer + a pretrained multilingual cross-encoder (e.g. `BAAI/bge-reranker-v2-m3` or the mMiniLM mMARCO cross-encoder) | zero-shot scores; threshold chosen on val | explain the choice: multilingual (RU/KK), cross-attention over the whole pair, size vs CPU latency |
| E3 fine-tuned transformer | the same cross-encoder, fine-tuned on train pairs | BCE loss, AdamW, lr 2e-5 (also try 1e-5 and 3e-5), batch 16–32, 2–3 epochs, warmup 10%, early stopping on val nDCG@10 | save the best checkpoint by val metric; 3 seeds; push to `<ns>/adilet-reranker-ft` |

Record the full configuration of every run in `config.yaml`: learning rate, batch size, epochs, optimizer, loss, seed, max length, hardware.

## Metrics (for every configuration)

- **Classification:** ROC-AUC, F1 (at the threshold tuned on val), PR-AUC.
- **Ranking** after reranking the fixed top-50: nDCG@10, MRR@10.
- **Cost:** training time; CPU inference latency for 30 candidates; parameter count; RAM.
- **Significance:** a paired randomization test on per-query nDCG@10 (ranx `compare`) for E3 vs E2 and E2 vs E1.
- **Stability:** mean ± std over 3 seeds.

## Error analysis

Take ≥ 10 wrong predictions from E3 and look at the same queries under E1. Tabulate them with: query, candidate, label, score, error type, likely cause, fix. Types to look for:

- a short or vague query;
- an unknown abbreviation or term (ИПН, КПН, МРП, ТОО, НДС…);
- an ambiguous query that spans several codes;
- near-duplicate articles across codes;
- Kazakh morphology or terminology;
- repealed vs current confusion;
- a labelling error (fix it in qrels and log the fix);
- class imbalance.

## Research questions: answer each explicitly, with numbers

- **RQ1.** Do dense embeddings beat the baseline representation (E1 vs E0)?
- **RQ2.** How much better is a pretrained transformer than classical ML (E2 vs E1)?
- **RQ3.** How much does fine-tuning help on this domain dataset, statistically and practically (E3 vs E2)?
- **RQ4.** Is the gain worth the compute? Compare Δ nDCG@10 against Δ latency/cost per query on CPU.

Also answer:
- Which model is the most stable?
- What limits this experiment?
- What should the next series of experiments change?

## Deliverables

- `ml/notebooks/A4_embeddings_to_finetuning.ipynb`: Colab-ready, runs top to bottom.
- Run folders for E0–E3; `results.csv` updated.
- Comparison charts:
  - metric bars with error bars;
  - latency-vs-quality scatter;
  - PR curves.
- `docs/report/A4_report.md` (2–3 pages) and `docs/presentation/A4_slides.md` (5–7 slides).
- The checkpoint link in the report.
- `docs/decisions.md`: which reranker goes to production, and why.

## Acceptance criteria

- [ ] 4 configurations, the same split, the same ≥ 2 metrics, all in one comparison table.
- [ ] The fine-tuned model is saved by its validation metric and linked from the report.
- [ ] Error analysis has ≥ 10 examples with categories and causes.
- [ ] RQ1–RQ4 are answered with numbers and significance tests.
