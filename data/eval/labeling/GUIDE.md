# Gold Labeling Guide

Use this guide for ML-03 retrieval and answer-quality evaluation.

## Unit Of Judgement

Judge relevance at `article_id` level, not chunk level. If any chunk from an article directly
answers the query, the article can receive relevance `3`.

## Relevance Grades

- `3`: directly answers the legal question with enough context for citation.
- `2`: contains an important rule or condition, but another article is needed for the full answer.
- `1`: topically related background only.
- `0`: not relevant or misleading for the query.

## Query Mix

For each major act and language, collect:

- plain citizen questions;
- professional/legal phrasing;
- citation-seeking queries, such as "article 114";
- synonym or paraphrase cases;
- negative/out-of-scope queries where the answer should be refused.

## Review Rules

- Prefer current `in_force` articles unless the query explicitly asks about repealed text.
- Keep Russian and Kazakh labels separate; do not copy labels across languages without review.
- Include all articles that must appear in a complete cited answer, not only the best single match.
- Flag ambiguous, obsolete or translation-sensitive queries for a second reviewer.

## Target Dataset

For the first real benchmark, aim for at least 200 queries:

- 100 Russian and 100 Kazakh;
- at least 30 cross-article questions;
- at least 30 hard negative queries;
- at least two reviewers for 20 percent of the set to estimate agreement.
