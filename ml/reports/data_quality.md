# Data Quality Report: Bootstrap Sample

Date: 2026-10-08  
Corpus version: `2026.10.08-bootstrap`

This is a bootstrap integration sample for Backend and Frontend. It follows the final
`contracts/data_schema.md` schema, but it is not the final scraped Tier-1 corpus and must not be
used for quality claims.

## Files

| File | Rows |
|---|---:|
| `data/sample/documents.parquet` | 2 |
| `data/sample/articles.parquet` | 30 |
| `data/sample/chunks.parquet` | 33 |
| `data/sample/sample_articles.json` | 30 |

## Coverage

- Languages: Russian and Kazakh.
- Act: Labor Code sample, `doc_id = K1500000414`.
- Included cases:
  - one excluded article in each language (`a53`);
  - amendment notes in each language (`a113`);
  - a long article split into multiple chunks (`a114`);
  - RU/KK `parallel_article_id` for every article.

## Validation

The sample was loaded through the backend corpus validator:

```text
2 documents, 30 articles, 33 chunks, corpus_version=2026.10.08-bootstrap
```

Known limitations:

- Text is educational bootstrap content, not official statute text.
- Article numbering gaps are intentional because this is a selected sample, not the full code.
- Real Adilet source anchors and revision parsing still need live scraper QA.
