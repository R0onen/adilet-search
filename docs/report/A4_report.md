# A4 Report: Query-Article Relevance Classification

## Task Framing

The A4 task is query-article relevance classification for reranking search candidates.

- `X`: query plus candidate article text/features.
- `y`: relevant when qrels relevance is at least 1.
- Candidates: article candidates from the first-stage retriever.
- Metrics: `roc_auc`, `f1`, `pr_auc`, plus ranking metrics after reranking.

## Local Seed Configuration

The implemented local classifier is `20261008_tfidf_logreg_seed`.

| Metric | Value |
|---|---:|
| `roc_auc` | 0.9072 |
| `f1` | 0.4898 |
| `pr_auc` | 0.7118 |
| `ndcg@10` | 0.8198 |
| `mrr@10` | 0.8500 |

Features:

- TF-IDF cosine;
- token overlap;
- BM25 score;
- query length;
- article length.

## RQ Answers From Local Seed Only

- RQ1: the learned TF-IDF feature model does not beat BM25 by nDCG@10 on the seed set
  (`0.8198` vs `0.8796`).
- RQ2: the bootstrap hash-dense path is below BM25 by nDCG@10 (`0.7872` vs `0.8796`).
- RQ3: fine-tuning is not measured locally because it requires GPU and labels.
- RQ4: local bootstrap inference is fast, but real transformer quality/latency tradeoffs remain
  unmeasured until the cross-encoder checkpoint is run.

## Required Next Configurations

The report structure is ready for:

- E0: TF-IDF/logistic baseline.
- E1: real embedding features plus classical ML.
- E2: zero-shot multilingual cross-encoder.
- E3: fine-tuned cross-encoder.

## Conclusion

The local A4 baseline and metrics are implemented. The full four-configuration A4 experiment is
blocked on real labels, downloaded transformer checkpoints and GPU runtime.
