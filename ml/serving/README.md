# ML service

Implements `contracts/ml_service.md`: `/health`, `/version`, `/metrics`, `/embed`, `/rerank`,
`/generate` (SSE or JSON).

## Run

In Docker, from the repository root (the real models; ~1.6 GB of weights download into the
`ml-model-cache` volume on the first start, which can take several minutes):

```bash
ML_SERVICE_URL=http://ml-service:8001 docker compose --profile ml up -d --build
```

Offline stand-ins instead of the models (no download; used by CI):

```bash
ML_MODEL_MANIFEST_PATH=/app/models/model_manifest.bootstrap.json ML_SERVICE_URL=http://ml-service:8001 docker compose --profile ml up -d --build
```

Switching between the two needs a reindex: the backend refuses an index built with other models.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_MANIFEST_PATH` | `/app/models/model_manifest.json` | which pipeline to run (in compose: `ML_MODEL_MANIFEST_PATH`) |
| `MODEL_CACHE_DIR`, `HF_HOME` | `/models`, `/models/hf` | where model weights are cached |
| `ADILET_ML_BATCH_SIZE` | `32` | embed/rerank batch size |
| `ADILET_ML_INFERENCE_WORKERS` | `2` | bounded parallel CPU model calls, off the ASGI event loop |
| `ADILET_ML_DEVICE` | `cpu` | `cpu` or explicit `cuda`; GPU image and NVIDIA runtime required for CUDA |
| `ADILET_ML_CPU_THREADS` | `4` (Compose) | OpenMP/MKL threads per inference call; tune with concurrency |
| `ADILET_ML_GENERATOR_MODE` | `fallback` | `openai` calls `LLM_BASE_URL`; `fallback` returns the first sentence of the top source |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | — | an OpenAI-compatible endpoint. The base URL is given **without** `/v1`: the service appends `/v1/chat/completions` |
| `MODEL_PROMPT_PATH` | `prompts/answer_v1.md` | the answer prompt (system rules + user template) |

If the models cannot be loaded (for example no network on the first start), the process stays up
and `/health` reports `down` with the reason, instead of crash-looping.

## Examples

```bash
curl http://localhost:8001/health
```

```bash
curl -X POST http://localhost:8001/embed -H "Content-Type: application/json" -d '{"texts":["Ответственность работодателя за задержку зарплаты"],"kind":"query"}'
```

```bash
curl -X POST http://localhost:8001/rerank -H "Content-Type: application/json" -d '{"query":"задержка зарплаты","candidates":[{"id":"K1500000414:ru:a113","text":"Заработная плата выплачивается не реже одного раза в месяц."}]}'
```

```bash
curl -N -X POST http://localhost:8001/generate -H "Content-Type: application/json" -d '{"question":"Как часто выплачивается зарплата?","lang":"ru","sources":[{"ref":1,"article_id":"K1500000414:ru:a113","title":"Статья 113","text":"Заработная плата выплачивается не реже одного раза в месяц."}],"stream":true}'
```
