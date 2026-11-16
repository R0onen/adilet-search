# Adilet ML

The ML side of Adilet Search:

- corpus import and schema validation (`adilet_ml.ingest`, `adilet_ml.data`);
- retrieval helpers and experiment scripts (`adilet_ml.retrieval`, `scripts/`);
- the internal `ml-service` API used by the backend (`adilet_ml.serving`, contract: `contracts/ml_service.md`);
- model manifests, the answer prompt, reports and notebooks.

## Pipelines 0.2.0 and 1.0.0

| Stage | Model | Notes |
|---|---|---|
| Dense embedder | `intfloat/multilingual-e5-base` (zero-shot, pinned revision) | 768-d, cosine, `query: ` / `passage: ` prefixes |
| Sparse encoder | BM25 term weights, Russian Snowball stemming | Kazakh tokens are not stemmed (no Snowball stemmer exists) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`: pretrained in 0.2.0, fine-tuned on our questions in 1.0.0 | top 5 fused articles, 256 tokens |
| Generator | any OpenAI-compatible LLM (`ADILET_ML_GENERATOR_MODE=openai`) | prompt: `prompts/answer_v1.md`; without an LLM, an extractive fallback |

`models/model_manifest.json` describes pipeline 1.0.0 and selects the implementations (`runtime`); its
reranker is our fine-tuned checkpoint on the Hugging Face Hub (`qb2k/adilet-reranker-mminilm-ru-kk`,
produced by `notebooks/A4_embeddings_to_finetuning.ipynb`). `models/model_manifest.pretrained.json`
is pipeline 0.2.0 with the pretrained reranker and the same index. See `MODEL_CARD.md`.
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
complete Labor Code). `--tier 2 --out ../data/processed_t2` builds the 40-act corpus
of the deployed index (20,490 articles, 41,074 chunks); `--all-acts` converts every act that is not
listed as expired.

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

Final evaluation through the running API (needs the stack up):

```bash
python ml/scripts/eval_api_synthetic.py <label> out.jsonl
```

```bash
python ml/scripts/eval_api_answers.py answers.jsonl --pause 20
```

The first measures search on the 195 LLM-written test questions of `data/eval/synthetic/`; the
second records generated answers for the human-approved questions. Results:
`docs/report/final_eval.md`.

## Limits

- No gold set written by lawyers. The test questions are LLM-written with automatic labels; a
  person reviewed 60 of them (`data/eval/labeling/`).
- Only the reranker is fine-tuned. The embedder is pretrained.
- Kazakh keyword matching is weaker than Russian (no stemmer); the dense embedder compensates.
