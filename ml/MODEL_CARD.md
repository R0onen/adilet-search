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

Only proxy numbers exist so far (`ml/reports/results.csv`). On the title-query test split (1,318
queries, searching article bodies), the BM25 stage alone reaches nDCG@10 0.730 (RU 0.753, KK 0.708)
and Recall@50 0.938. The dense, hybrid and reranked stages have not been measured on a fair set
yet: title queries are unfair to them in one direction (legislator's wording) and too easy through
the product index (the title is in every chunk header). There is no human gold set.

## Known limits

- Zero-shot models: nothing is tuned to legal Kazakh or Russian.
- Kazakh keyword matching is weaker (no stemmer), and the reranker never saw Kazakh in training.
- Articles longer than the encoders' context are split into chunks; a chunk can miss context.
- The generator can still misread a source. The backend removes citations to sources that were not
  provided, but cannot check that a cited source supports the claim.
- Only 8 codes are indexed by default; questions about other acts get weak results.
