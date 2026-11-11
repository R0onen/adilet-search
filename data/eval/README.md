# Evaluation data

Built by `python ml/scripts/build_title_eval.py` from `data/processed/`.

- `queries.jsonl`: 8,735 queries. Each is the official title of an article (`source: "title"`).
- `qrels.jsonl`: the article the title belongs to is relevant (3). Nothing else is labelled.
- `splits.json`: 70/15/15 by `doc_id:unit_key` (the RU and KK versions of an article stay in the
  same subset), stratified by document, seed 42, with the SHA-256 of both files.

These are **proxy labels**, not human judgements. Titles use the legislator's words, so they favour
keyword methods, and the product index embeds the title in every chunk header. Report numbers from
this set as "title-query (proxy) evaluation" and evaluate against article bodies.

`labeling/GUIDE.md` describes the human gold set (plain-language questions with graded relevance),
which does not exist yet.
