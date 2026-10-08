# ML Slides Section

## Problem

Keyword search misses legal answers when the user wording differs from statute wording. The ML
module adds hybrid retrieval, reranking and grounded generation over cited sources.

## Dataset

Bootstrap data: 2 documents, 30 articles and 33 chunks. Final target: Tier-1 Kazakhstan codes in
RU and KK.

## Model

Current bootstrap: hash dense vectors, BM25 sparse vectors, reciprocal-rank fusion, lexical rerank
fallback and extractive citation generation. Final path: fine-tuned bi-encoder, cross-encoder and
QLoRA/GGUF generator.

## Experimental Results

| Run | nDCG@10 | Recall@10 | MRR@10 |
|---|---:|---:|---:|
| BM25 | 0.8796 | 0.8889 | 0.9000 |
| Hash dense | 0.7872 | 0.9444 | 0.8167 |
| TF-IDF LogReg | 0.8198 | 1.0000 | 0.8500 |

## Final Model

The final served version currently remains `0.1.0-bootstrap`. It is integration-ready but not a
production-quality legal model.

## Performance

Local hash bootstrap p95: `/embed` 3.9 ms for one query and `/rerank` 4.6 ms for 30 candidates.

## Limitations

No full official corpus, human gold set, HF checkpoint upload, GPU fine-tuning or deployed API
evaluation yet.
