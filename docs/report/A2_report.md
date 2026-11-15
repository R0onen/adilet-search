# Assignment 2: data preparation and baseline

Assignment 2 and the midterm were submitted earlier in the course. This page records the data and the baseline that the later assignments build on, with the numbers as they are in the repository now.

## Data

- **Source.** AdiletCodex v1.0 (CC BY 4.0), the official texts parsed from adilet.zan.kz, snapshot of 17 September 2026. Downloaded and verified by `ml/scripts/download_data.py`.
- **Corpus for experiments.** The 8 main codes in Russian and Kazakh: 16 documents, 9,259 articles, 16,264 chunks of about 400 tokens.
- **Unit.** One article of one act in one language. Long articles are split into chunks for retrieval and collapsed back to the article in the results.
- **Quality.** No duplicate ids, empty texts or orphan chunks; 9,248 of 9,259 articles have a parallel article in the other language (`ml/reports/data_quality.md`).
- **Cleaning.** Texts are stored verbatim. Amendment footnotes are separated from the article text.

## Evaluation data and split

- **Title queries** (`data/eval/`): each article's title is a query for that article, 8,735 queries. A proxy: titles use the statute's own wording.
- **Split.** By article, 70 / 15 / 15, seed 42; the Russian and Kazakh versions of an article are in the same split. This prevents leakage between the two languages of one article.

## Baseline

BM25 over article bodies with Russian stemming, on the 1,318 test title queries (`ml/reports/results.csv`):

| Metric | All | Russian | Kazakh |
|---|---|---|---|
| nDCG@10 | 0.730 | 0.753 | 0.708 |
| MRR@10 | 0.686 | 0.709 | 0.664 |
| Recall@10 | 0.866 | 0.891 | 0.842 |
| Recall@50 | 0.938 | 0.947 | 0.929 |

nDCG@10 is the main metric because the position of the right article matters; recall shows whether it was retrieved at all. Accuracy is not used: almost every (query, article) pair is negative.

## What followed

Title queries overstate keyword search, so Assignments 3 and 4 use 803 LLM-written questions in everyday and legal wording (`data/eval/synthetic/`), 60 of them reviewed by a person. See `A3_report.md` and `A4_report.md`.
