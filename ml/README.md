# Adilet ML

This package owns the ML side of Adilet Search:

- corpus ingestion and schema validation;
- sparse/dense retrieval helpers and experiment code;
- the internal `ml-service` API consumed by the backend;
- model manifests, prompt templates, reports and notebooks.

The current implementation is a contract-complete offline v0. It uses deterministic local
embeddings and overlap reranking by default so the backend can index/search without downloading
large models. Set `ADILET_ML_EMBEDDER_BACKEND=sentence-transformers` after fetching model weights
to switch the same service to the real zero-shot embedder.

## Quick Start

```bash
cd ml
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

Run the service from the repository root:

```bash
python -m uvicorn adilet_ml.serving.app:app --app-dir ml/src --host 0.0.0.0 --port 8001
```

Generate the bootstrap sample:

```bash
python -m adilet_ml.data.sample_builder --out data/sample
```

Fetch and build the first official cached corpus slice:

```bash
python ml/scripts/build_corpus.py --fetch --limit-acts 1
```

Run the seed lexical retrieval baseline:

```bash
python ml/scripts/run_bm25_baseline.py --data-dir data/sample --queries data/eval/queries.jsonl --qrels data/eval/qrels.jsonl
```

## Important Limits

The committed sample is a bootstrap integration fixture, not the final scraped Tier-1 corpus.
The seed eval set is only a wiring check. Real data collection still needs the polite Adilet
scraper in `adilet_ml.ingest` plus human review of parser QA, Kazakh labels and gold relevance
judgements.
