# Data layout

Data follows `contracts/data_schema.md`. Source: **AdiletCodex v1.0** (CC BY 4.0,
https://doi.org/10.5281/zenodo.22812626), the official texts of the codes and laws of Kazakhstan
parsed from adilet.zan.kz. Texts are stored verbatim.

- `data/raw/adiletcodex/`: the downloaded source file. Git-ignored.
- `data/sample/`: committed sample for integration and CI: the complete Labor Code, RU + KK
  (2 documents, 454 articles, 805 chunks).
- `data/processed/`: the full corpus: the 8 Tier-1 codes, RU + KK (16 documents, 9,259 articles,
  16,264 chunks). Git-ignored; rebuild with `python ml/scripts/download_data.py`.
- `data/eval/`: evaluation queries, relevance labels and splits (see its README).
- `data/MANIFEST.json`: checksums and row counts.
