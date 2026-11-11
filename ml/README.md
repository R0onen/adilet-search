# Adilet ML

The ML side of Adilet Search:

- corpus import and schema validation (`adilet_ml.ingest`, `adilet_ml.data`);
- retrieval helpers and experiment scripts (`adilet_ml.retrieval`, `scripts/`);
- the internal `ml-service` API used by the backend (`adilet_ml.serving`, contract: `contracts/ml_service.md`);
- model manifests, the answer prompt, reports and notebooks.

## Pipeline 0.2.0

| Stage | Model | Notes |
|---|---|---|
| Dense embedder | `intfloat/multilingual-e5-base` (zero-shot, pinned revision) | 768-d, cosine, `query: ` / `passage: ` prefixes |
| Sparse encoder | BM25 term weights, Russian Snowball stemming | Kazakh tokens are not stemmed (no Snowball stemmer exists) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (zero-shot, pinned revision) | top 20 fused articles, 384 tokens |
| Generator | any OpenAI-compatible LLM (`ADILET_ML_GENERATOR_MODE=openai`) | prompt: `prompts/answer_v1.md`; without an LLM, an extractive fallback |

`models/model_manifest.json` describes this pipeline and selects the implementations (`runtime`).
`models/model_manifest.bootstrap.json` runs offline stand-ins (hash embedder, word-overlap
reranker) for tests and CI. It has its own `index_compat_id`, so an index built with the stand-ins
is never served as E5.

## Quick start

```bash
cd ml && uv sync --extra dev && uv run pytest
```

Build the corpus (downloads AdiletCodex v1.0 from Zenodo, verifies its MD5; no token needed):

```bash
uv run python scripts/download_data.py
```

That writes the 8 Tier-1 codes in RU + KK to `data/processed/` (16 documents, 9,259 articles,
16,264 chunks). `--docs K1500000414 --out ../data/sample` rebuilds the committed sample (the
complete Labor Code). `--all-acts` converts all 343 acts.

Run the service (offline stand-ins; add `--extra models` and drop the variable for the real models):

```bash
MODEL_MANIFEST_PATH=models/model_manifest.bootstrap.json uv run uvicorn adilet_ml.serving.app:app --port 8001
```

In Docker the service is the `ml` profile of the root `docker-compose.yml`; see `serving/README.md`.

## Evaluation

```bash
uv run python scripts/build_title_eval.py
```

```bash
uv run python scripts/run_bm25_baseline.py --run-dir experiments/<date>_bm25_title_test
```

```bash
uv run python scripts/aggregate_results.py
```

`data/eval/` holds title queries (each article's title is a query for that article), split 70/15/15
by article. These are proxy labels: see the caveats at the top of `scripts/build_title_eval.py`.
Every run writes `experiments/<run>/{metrics.json,config.yaml,env.json}`; `reports/results.csv`
aggregates them. Report only numbers that are in that table.

## Limits

- No human gold set yet (`data/eval/labeling/GUIDE.md`); all current numbers are proxy numbers.
- The embedder and reranker are zero-shot. Fine-tuning runs on a GPU (Colab/Kaggle), not here.
- Kazakh keyword matching is weaker than Russian (no stemmer); the dense embedder compensates.
