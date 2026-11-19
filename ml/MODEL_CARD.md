# Model card: Adilet Search pipeline 1.0.0

Manifest: `ml/models/model_manifest.json` · `index_compat_id`: `e5base-bm25st-ch1` · 16 November 2026

The previous pipeline, `0.2.0` (`ml/models/model_manifest.pretrained.json`), differs only in the reranker weights: it serves the pretrained reranker. Both use the same index.

## What it does

Retrieves articles of Kazakhstan legislation for a question in Russian or Kazakh, and writes a short answer that cites the retrieved articles. It is a search aid, not legal advice.

## Components

| Stage | Model | Training |
|---|---|---|
| Query expansion | a dictionary of 34 everyday words and abbreviations with their legal terms (`backend/app/services/query_expansion.py`) | written by hand |
| Dense embedder | `intfloat/multilingual-e5-base` @ `d1287505` | pretrained, not fine-tuned |
| Sparse encoder | BM25 term weights; Russian Snowball stemming; Kazakh unstemmed | no training |
| Fusion | weighted reciprocal-rank fusion, `k = 60`, weights 1:1 (in the backend) | no training |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` @ `1427fd65`, **fine-tuned by us** and published as [`qb2k/adilet-reranker-mminilm-ru-kk`](https://huggingface.co/qb2k/adilet-reranker-mminilm-ru-kk) @ `d5ea1420`; reranks the first 5 fused articles at 256 tokens | 4,264 (question, article) pairs from LLM-written questions, learning rate 1e-5, 2 epochs; Assignment 4, configuration E3b |
| Generator | an OpenAI-compatible LLM chosen at deployment (`LLM_MODEL`) with `prompts/answer_v1.md` | not trained by us |

The fine-tuned weights (470 MB) are on the Hugging Face Hub and download on the first start. `ml/notebooks/A4_embeddings_to_finetuning.ipynb` reproduces them in about 2 minutes on a GPU.

## Data

AdiletCodex v1.0 (CC BY 4.0, doi:10.5281/zenodo.22812626), parsed from adilet.zan.kz, `corpus_version` 2026.09.17. Texts are verbatim; amendment footnotes are stored separately. Later amendments are not in the snapshot.

| Corpus | Acts | Articles (RU + KK) | Chunks | Used for |
|---|---|---|---|---|
| Tier 1 (default of the importer) | 8 codes | 9,259 | 16,264 | training and all offline experiments |
| Tier 2 (`--tier 2`) | 40 acts: 23 codes and 17 laws that everyday questions are about (family, consumer protection, housing, road traffic, enforcement, bankruptcy and others) | 20,490 | 41,074 | the deployed index |

## Evaluation

All test numbers are on 195 LLM-written test questions (articles not seen in training; 41% Kazakh). The label is the article a question was written for. A person checked 60 of them: 53 correct, 3 wrong, 4 too vague (`data/eval/labeling/`).

**Reranker, offline** (20 BM25 candidates, tier 1; `docs/report/A4_report.md`):

| Reranker | nDCG@10 | ROC-AUC | F1 |
|---|---|---|---|
| TF-IDF features + Logistic Regression | 0.727 | 0.923 | 0.539 |
| Pretrained cross-encoder | 0.867 | 0.959 | 0.598 |
| Fine-tuned on written questions (served) | 0.880 | 0.973 | 0.652 |

The fine-tuned model is better than the pretrained one by +0.013 nDCG@10 (95% interval +0.003 to +0.025, p = 0.016).

**Whole pipeline through the live API** (hybrid mode, 5 reranked candidates; `ml/experiments/final-selection/`):

| Index | Reranker | Right article first | nDCG@10 | Recall@10 | Human-approved subset: first / nDCG@10 |
|---|---|---|---|---|---|
| 8 codes | pretrained | 0.831 | 0.885 | 0.944 | 0.811 / 0.890 |
| 8 codes | fine-tuned | 0.851 | 0.895 | 0.944 | 0.830 / 0.902 |
| 40 acts (deployed) | fine-tuned | 0.826 | 0.871 | 0.928 | 0.830 / 0.908 |

Adding 32 acts costs 2.5 points of "right article first" on questions written for the 8 codes, because other acts regulate the same subjects. On the human-approved questions the result is unchanged.

On 55 everyday questions about the added acts (`data/eval/everyday/`, written inside the project) the right article is first for 58% and in the top 10 for 87%, against 26% and 64% for keyword search alone.

Earlier comparisons of embedding models and of the hybrid pipeline on title-derived queries are in `docs/report/RESEARCH_FINDINGS.md`.

## Known limits

- The test questions are LLM-written with one labelled article each; a second correct article counts as an error. Differences below about 0.02 are within noise.
- Kazakh is weaker than Russian at every stage: no stemmer for keyword matching, and neither the embedder nor the reranker base was trained on much Kazakh. The reranker's offline nDCG@10 is 0.83 in Kazakh against 0.91 in Russian.
- Everyday questions about acts outside the 8 codes are answered less well than the synthetic test suggests. Retraining the reranker with questions about those acts did not change that (`ml/experiments/reranker-40acts/`): the limit is retrieval and colloquial wording, not the reranker's training data.
- The query dictionary is small and mostly Russian. A question in words that are neither in the article nor in the dictionary still depends on the dense embedder alone.
- The reranker reads only the first 5 fused articles. Reranking 10 puts the right article first for 0.856 of the questions on the deployed index, at about half the throughput (`SEARCH_RERANK_TOP_N`).
- Articles longer than the encoders' context are split into chunks; a chunk can miss context.
- The generator can misread a source. The backend removes citations to sources that were not provided, but cannot check that a cited source supports the claim.
- Acts outside the 40 are not indexed.
