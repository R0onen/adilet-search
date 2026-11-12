# Model card: Adilet Search pipeline 0.2.0

Manifest: `ml/models/model_manifest.json` · `index_compat_id`: `e5base-bm25st-ch1` · 2026-11-11

## What it does

Retrieves articles of Kazakhstan legislation for a question in Russian or Kazakh, and writes a short
answer that cites the retrieved articles. It is a search aid, not legal advice.

## Components

| Stage | Model | Training |
|---|---|---|
| Dense embedder | `intfloat/multilingual-e5-base` @ `d1287505` | pretrained, zero-shot (not fine-tuned on our data) |
| Sparse encoder | BM25 term weights; Russian Snowball stemming; Kazakh unstemmed | no training |
| Fusion | weighted reciprocal-rank fusion, `k = 60`, weights 1:1 (in the backend) | no training |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` @ `1427fd65` | pretrained on mMARCO (14 languages, Russian included, Kazakh not), zero-shot |
| Generator | an OpenAI-compatible LLM chosen at deployment (`LLM_MODEL`) with `prompts/answer_v1.md` | not trained by us |

## Data

AdiletCodex v1.0 (CC BY 4.0, doi:10.5281/zenodo.22812626), parsed from adilet.zan.kz: the 8 Tier-1
codes in Russian and Kazakh, 9,259 articles, 16,264 chunks of about 400 tokens. Texts are verbatim;
amendment footnotes are stored separately. The corpus is a snapshot (`corpus_version` 2026.09.17):
later amendments are not in it.

## Evaluation

The full body-only frozen proxy study now compares pretrained models and project ablations:

| Configuration | Validation nDCG@10 | Test nDCG@10 |
|---|---:|---:|
| E5 dense | 0.706 | 0.703 |
| Project hybrid + reranker | 0.856 | 0.846 |
| Hybrid without reranker | 0.778 | 0.770 |
| Qwen3-Embedding-0.6B | 0.539 | 0.548 |
| BGE-M3 | 0.830 | 0.822 |
| EmbeddingGemma 2, text-only | 0.710 | 0.716 |

All use the same 16,264 body-only chunks, 1,311 validation and 1,318 test queries. The hybrid
configuration is selected by validation; its paired test difference from dense E5 is +0.142,
with an article-family bootstrap 95% interval [+0.123, +0.162]. It reproduces the project stages
offline using local BM25; its IDF differs from Qdrant. The optional LLM rewrite has only a
separate eight-test-query pilot and establishes no benefit.

Queries remain title-derived known-item proxies. Body-only indexing avoids direct title-header
overlap, but there is no independent human-gold set. These scores do not establish general
natural-language legal accuracy. Encoder precision is FP16 except Gemma's supported BF16;
this evaluates practical configurations, not architecture alone. Checkpoints, fingerprints,
per-language scores, rankings and limits are in
[research findings](../docs/report/RESEARCH_FINDINGS.md) and
[run artifacts](experiments/research-final/results.json).

The earlier article-body BM25 baseline (`ml/reports/results.csv`, test nDCG@10 0.730) uses a
different retrieval unit. Keep it separate from this matched chunk-based comparison.

## Known limits

- Zero-shot models: nothing is tuned to legal Kazakh or Russian.
- Kazakh keyword matching is weaker (no stemmer), and the reranker never saw Kazakh in training.
- Articles longer than the encoders' context are split into chunks; a chunk can miss context.
- The generator can still misread a source. The backend removes citations to sources that were not
  provided, but cannot check that a cited source supports the claim.
- Only 8 codes are indexed by default; questions about other acts get weak results.
