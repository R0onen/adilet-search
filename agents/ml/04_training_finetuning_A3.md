# ML-04: Model comparison, tuning, fine-tuning, QLoRA (Assignment 3: Model Training & Fine-Tuning), week 4

**Goal:** find the best retriever and build the generator, with every A3 rubric item visibly covered. Everything uses the **same splits and the same metrics** as ML-03.

## A3 rubric checklist

| Criterion | Points | Covered by |
|---|---|---|
| Compare ≥ 3 models/configs, same split + metrics | 15 | R0–R5 |
| Hyperparameter tuning (search space + best params) | 15 | BM25 grid; Optuna for fusion and LightGBM; fine-tuning grid |
| Fine-tuning (lr, batch, epochs, optimizer, loss) | 15 | R4 |
| Transfer learning (what transfers, why this base) | 10 | R2/R4 section |
| LoRA/QLoRA for the LLM (r, alpha, dropout, targets, trainable params, why PEFT) | 15 | G1 |
| Classical ML optimisation, before/after | 10 | R0, R1 |
| Unified results table, ≥ 2 shared metrics | 10 | `results.csv` → report |
| Scientific interpretation | 5 | report |
| Reproducibility (seeds, versions, configs) | 3 | run folders |
| Oral defence | 2 | `qa_ml.md` (ML-07) |

## Retrieval experiments

| ID | Configuration |
|---|---|
| R0 | BM25 with defaults (k1 = 1.2, b = 0.75), then tuned by grid: k1 ∈ {0.6, 0.9, 1.2, 1.5, 2.0}, b ∈ {0.3, 0.5, 0.75, 0.9, 1.0} |
| R1 | the TF-IDF+LogReg reranker from ML-03, and LightGBM on the same features: before and after tuning (LogReg: C, class_weight; LightGBM: num_leaves, learning_rate, min_child_samples, n_estimators; GridSearch or Optuna ≥ 30 trials; GroupKFold by group key) |
| R2 | zero-shot dense: ≥ 3 pretrained multilingual encoders, e.g. `intfloat/multilingual-e5-base`, `intfloat/multilingual-e5-large` or `BAAI/bge-m3`, `sentence-transformers/LaBSE` (+ a Russian-adapted encoder if one is available). Measure CPU query latency for each |
| R3 | hybrid: tuned BM25 + the best dense encoder, weighted RRF (contract §2); tune `rrf_k` ∈ [10, 100] and the weights with Optuna on val |
| R4 | fine-tuned bi-encoder (the best zero-shot base that meets the CPU budget) |
| R5 | hybrid with the fine-tuned dense encoder: the final retriever candidate |

### R4: fine-tuning details (report all of these)

- **Data:** (synthetic query, positive chunk) pairs from train groups, plus 1–3 hard negatives per pair: the BM25 top-30 minus the positives, excluding any chunk of the same group.
- **Loss:** MultipleNegativesRankingLoss (InfoNCE over in-batch + hard negatives), scale 20. Use CachedMNRL if the GPU limits the batch size.
- **Optimizer and schedule:** AdamW with linear warmup of 10%, fp16.
- **Search space:** lr ∈ {1e-5, 2e-5, 5e-5}, epochs ∈ {1, 2, 3}, effective batch ∈ {32, 64, 128}.
  - A small grid or Optuna, ≤ 8 trials on a subset. State the search space and the best parameters.
  - Then run the best config with 3 seeds and report mean ± std.
- **Checkpointing:** evaluate val nDCG@10 every N steps and keep the best checkpoint. Push it to `<ns>/adilet-embedder-ft` with a model card.
- **Transfer learning section** in the report:
  - what the pretrained encoder already knows (multilingual semantic similarity learned from large weakly-supervised pair data, including RU and KK text);
  - what fine-tuning adapts (legal vocabulary, statute style, the mapping from a lay question to the provision);
  - why this base (languages covered, size vs CPU latency, max sequence length, license).

## Generator experiments (G0 vs G1)

- **Pick the base model.** Choose an open ~7–8B instruct model with strong Russian (for example, the Qwen family; also consider ISSAI's KazLLM for Kazakh).
  - First compare two candidates zero-shot on 20 val questions, including KK.
  - Check each license.
  - Record the choice in `docs/decisions.md`.
- **SFT data** in `data/sft/{train,val}.jsonl` (the `data_schema.md` §7 format):
  - Each example is a question + the top-5 articles retrieved by R3/R5 for **train-split** queries → a grounded answer with `[n]` citations.
  - ~15% are cases where the sources do not contain the answer, with an explicit refusal.
  - Produce them with a teacher LLM, then auto-filter:
    - citation markers are valid;
    - each cited source contains the key terms of its claim;
    - the language matches.
  - Have humans review 100. Target 1.5–3k examples.
- **QLoRA configuration** (print all of it):
  - 4-bit NF4 with double quantisation; fp16/bf16 compute dtype.
  - LoRA r = 16, alpha = 32, dropout = 0.05.
  - Target modules `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`.
  - lr 2e-4 with cosine schedule and 3% warmup, 2 epochs, effective batch 16, max sequence length ~3072 (lower it if memory demands).
  - Gradient checkpointing.
  - **Print the trainable vs total parameters (count and %).**
- **Why PEFT, not full fine-tuning** (write this in the report):
  - Full fine-tuning of a 7B model needs >100 GB of GPU memory with optimizer states; QLoRA fits on a T4/L4.
  - It overfits less on a small SFT set.
  - The adapter is tens of MB, versionable and swappable on the same base.
- **Evaluate G0 vs G1** on the gold val/test questions, answerable and unanswerable:
  - `citation_validity` (markers refer to real sources);
  - `citation_precision` (the cited article is in the relevant qrels);
  - `faithfulness` (LLM-as-judge on all; a human checks 30);
  - `refusal_accuracy`;
  - `rouge_l` against reference answers where they exist;
  - TTFT and tokens/s.
- Push the adapter to `<ns>/adilet-generator-qlora`.

## Deliverables

- Notebooks `A3_retrieval_experiments.ipynb` (R0–R5) and `A3_qlora_generator.ipynb` (G0/G1). Both Colab-ready, seeds fixed, library versions printed.
- Checkpoints on the HF Hub, with model cards.
- `ml/reports/results.csv` updated. `docs/report/A3_report.md` with:
  - **the unified table:** baseline / tuned / fine-tuned / transfer / LLM rows, with at least nDCG@10 and Recall@10 for every retrieval row;
  - charts;
  - **a scientific interpretation:** which change gave the biggest gain and why. Check these hypotheses against the data:
    - dense retrieval helps most on plain-language queries;
    - fine-tuning helps on terminology and KK;
    - hybrid keeps article-number queries correct;
  - the search space and best parameters for every tuned model.
- `docs/presentation/A3_slides.md`.
- `docs/decisions.md` updated with the current best retriever and generator.
- Optional: bump `model_manifest.json` to 0.2.0 if R5/G1 are already better and fit the latency budget. Tell Backend if `index_compat_id` changed (that means a reindex).

## Acceptance criteria

- [ ] Every run is in `ml/experiments/` with config, metrics and env.
- [ ] ≥ 3 configs were compared on the same split, and the search spaces and best parameters are stated.
- [ ] The LoRA parameters and trainable-parameter count are shown.
- [ ] Every result can be reproduced from the notebooks.
