# Data Layout

Data follows `contracts/data_schema.md`.

- `data/raw/adilet/{ru,kk}/`: cached source HTML from Adilet. Git-ignored.
- `data/sample/`: small committed integration sample for Backend and Frontend.
- `data/processed/`: full processed corpus. Git-ignored; publish through the private HF dataset.
- `data/eval/`: seed evaluation queries, qrels, splits and labelling instructions.
- `data/index/`: precomputed embeddings. Git-ignored; publish through the private HF dataset.
- `data/MANIFEST.json`: checksums and row counts for the latest committed sample or release.

The current sample is a bootstrap fixture for integration. It has the final schema, includes RU and
KK articles, parallel ids, an excluded article, amendment notes and a long split article. Replace it
with scraped Adilet text before reporting quality metrics. The committed eval set is a baseline
wiring check, not a real benchmark.
