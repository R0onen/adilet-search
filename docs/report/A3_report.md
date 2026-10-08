# A3 Report: Training and Fine-Tuning Plan With Local Seed Results

## Completed Locally

Three reproducible local configurations have been compared on the same seed qrels:

| Run | nDCG@10 | Recall@10 | MRR@10 | Role |
|---|---:|---:|---:|---|
| `20261008_bm25_seed` | 0.8796 | 0.8889 | 0.9000 | keyword baseline |
| `20261008_hash_dense_seed` | 0.7872 | 0.9444 | 0.8167 | dense-path bootstrap |
| `20261008_tfidf_logreg_seed` | 0.8198 | 1.0000 | 0.8500 | learned reranker baseline |

The current seed result favours BM25 by nDCG@10. This is expected because the tiny sample queries
share many exact terms with the relevant bootstrap articles.

## Fine-Tuning Configuration To Run On GPU

Retriever fine-tuning:

- Base: best zero-shot multilingual encoder after live comparison.
- Loss: MultipleNegativesRankingLoss with hard negatives.
- Search: learning rate `{1e-5, 2e-5, 5e-5}`, epochs `{1, 2, 3}`, effective batch
  `{32, 64, 128}`.
- Optimizer: AdamW, linear warmup 10 percent, fp16.

Generator QLoRA:

- Base: open instruct model with strong Russian/Kazakh support after license check.
- Quantization: 4-bit NF4 with double quantization.
- LoRA: `r=16`, `alpha=32`, `dropout=0.05`.
- Targets: `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`.
- Schedule: `lr=2e-4`, cosine, 3 percent warmup, 2 epochs.

## Blocked External Items

- Human-labelled gold data.
- HF namespace/token for datasets and checkpoints.
- Colab/Kaggle GPU run.
- Teacher LLM or API for synthetic SFT data.

## Conclusion

The repository now contains the code and run-folder structure needed for A3, plus local seed
comparisons. Final A3 marks that require actual fine-tuned checkpoints must be completed after GPU
and label access.
