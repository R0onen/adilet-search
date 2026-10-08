# A2 Report: Data Preparation and Baselines

## Task

Prepare the legal-search dataset shape and establish local baselines for article retrieval.

## Data

The committed bootstrap corpus contains 2 document rows, 30 article rows and 33 chunk rows under
`data/sample`. It covers Russian and Kazakh Labor Code sample text and includes parallel article
ids, an excluded article, amendment notes and a long split article.

Evaluation uses `data/eval/queries.jsonl` with 10 seed synthetic queries and
`data/eval/qrels.jsonl` with graded qrels. `data/eval/splits.json` freezes the seed split by
`doc_id:unit_key`. This is not a full gold benchmark.

## Baselines

| Run | nDCG@10 | Recall@10 | Recall@50 | MRR@10 |
|---|---:|---:|---:|---:|
| `20261008_bm25_seed` | 0.8796 | 0.8889 | 0.9444 | 0.9000 |
| `20261008_tfidf_logreg_seed` | 0.8198 | 1.0000 | 1.0000 | 0.8500 |

BM25 is the strongest seed baseline by nDCG@10. The learned TF-IDF/logistic baseline retrieves all
positive articles within the top 10 but ranks them slightly worse on this tiny set.

## Metrics

- `ndcg@10`: primary metric because it rewards relevant articles near the top.
- `recall@10` and `recall@50`: whether the answer article was retrieved at all.
- `mrr@10`: rank of the first relevant article.
- `roc_auc`, `f1`, `pr_auc`: classification metrics for the learned reranker.

Accuracy is not used because retrieval has many negatives and the ranking order matters more than a
single class decision.

## Conclusion

The A2 local pipeline is complete for a reproducible seed benchmark: data schema, qrels, splits,
baseline scripts, run folders and aggregated results all exist. The full A2 benchmark still needs
150+ human-labelled gold queries over the official Tier-1 corpus.
