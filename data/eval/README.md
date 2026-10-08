# Retrieval Evaluation Data

This folder starts the ML evaluation track for Adilet Search.

The committed files are a tiny seed set over `data/sample/` so the retrieval tooling can be run
end to end before the real Tier-1 corpus and human labels exist.

- `queries.jsonl`: query id, language and user-style query text.
- `qrels.jsonl`: graded article relevance. Use `3` for directly answers, `2` for strongly
  related, `1` for weak/supporting context and `0` for judged non-relevant.
- `labeling/GUIDE.md`: instructions for expanding labels after official Adilet scraping.

Run the lexical baseline from the repository root:

```bash
python ml/scripts/run_bm25_baseline.py --data-dir data/sample --queries data/eval/queries.jsonl --qrels data/eval/qrels.jsonl
```
