# Data quality report

Corpus: AdiletCodex v1.0 (CC BY 4.0, doi:10.5281/zenodo.22812626), parsed from adilet.zan.kz; `corpus_version` 2026.09.17. Built by `ml/scripts/download_data.py`, which verifies the MD5 of the download. Schema: `contracts/data_schema.md`.

## Tier 1 (8 codes; training and experiments)

Audit of 12 November 2026 (`docs/report/final_data_audit.json`):

| Check | Result |
|---|---|
| Documents (code × language) | 16 |
| Articles | 9,259 (4,631 Russian, 4,628 Kazakh) |
| Chunks | 16,264 |
| Duplicate article ids / chunk ids | 0 / 0 |
| Chunks without an article | 0 |
| Articles with empty text | 0 |
| Russian–Kazakh parallel links | 9,248, none broken |
| Articles in more than one evaluation split | 0 |

## Tier 2 (40 acts; the deployed index)

80 documents, 20,490 articles, 41,074 chunks. The importer applies the same schema validation; the indexer validated these counts before indexing (15 November 2026). The 51 acts that the full dataset holds in an expired or superseded edition (for example the 2017 Tax Code) are listed under `excluded_acts` in `ml/configs/corpus.yaml` and are never imported.

## Evaluation sets

| Set | Size | Labels |
|---|---|---|
| `data/eval/` title queries | 8,735 (6,106 train, 1,311 validation, 1,318 test) | each article's title is a query for that article (proxy) |
| `data/eval/synthetic/` | 803 questions for 400 articles (489 train, 119 validation, 195 test; 316 Kazakh) | LLM-written; the source article is the only relevant one |
| `data/eval/labeling/synthetic_review.csv` | 60 of the test questions | reviewed by a person: 53 correct, 3 wrong article, 4 too vague |

Both sets are split by article (70 / 15 / 15, seed 42), with the Russian and Kazakh versions of an article in the same split.

## Known limits

- The corpus is a snapshot; amendments after 17 September 2026 are not in it, and all articles carry the status "in force" as of the snapshot.
- Amendment footnotes are stored separately from the article text; texts are verbatim.
- 11 articles have no parallel article in the other language.
- There is no gold set written by lawyers.
