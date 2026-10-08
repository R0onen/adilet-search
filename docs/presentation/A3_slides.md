---
marp: true
title: A3 Training and Fine-Tuning
---

# A3: Training Plan

- Local seed comparison is reproducible
- Real fine-tuning path is specified
- GPU and labels are the remaining external dependencies

---

# Compared Locally

| Run | nDCG@10 | Recall@10 |
|---|---:|---:|
| BM25 | 0.8796 | 0.8889 |
| Hash dense | 0.7872 | 0.9444 |
| TF-IDF LogReg | 0.8198 | 1.0000 |

---

# Fine-Tuning Plan

- Bi-encoder: MNRL with BM25 hard negatives
- Search: learning rate, epochs, batch size
- Generator: QLoRA with NF4, LoRA r=16, alpha=32

---

# Current Selection

For the bootstrap pipeline, keep BM25 plus lexical fallback because it is fastest and strongest on
the seed set. Switch to the fine-tuned hybrid pipeline only after gold validation improves.

<!-- source: docs/report/A3_report.md -->
