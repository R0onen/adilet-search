# ML Service

Run locally from the repository root:

```bash
python -m uvicorn adilet_ml.serving.app:app --app-dir ml/src --host 0.0.0.0 --port 8001
```

By default this service uses deterministic local embeddings and overlap reranking. To run the real
zero-shot embedder after fetching weights, set:

```bash
ADILET_ML_EMBEDDER_BACKEND=sentence-transformers
MODEL_CACHE_DIR=.cache/models
```

## Curl Examples

```bash
curl http://localhost:8001/health
curl http://localhost:8001/version
curl http://localhost:8001/metrics
```

```bash
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"texts":["Ответственность работодателя за задержку зарплаты"],"kind":"query"}'
```

```bash
curl -X POST http://localhost:8001/rerank \
  -H "Content-Type: application/json" \
  -d '{"query":"задержка зарплаты","candidates":[{"id":"K1500000414:ru:a113","text":"зарплата выплачивается работнику"}]}'
```

```bash
curl -N -X POST http://localhost:8001/generate \
  -H "Content-Type: application/json" \
  -d '{"question":"Что с зарплатой?","lang":"ru","sources":[{"ref":1,"article_id":"K1500000414:ru:a113","title":"Статья 113","text":"Заработная плата выплачивается работнику не реже одного раза в месяц."}],"stream":true}'
```

## OpenAI-Compatible LLM

Set these env vars to use llama.cpp, vLLM or a hosted OpenAI-compatible endpoint:

```bash
ADILET_ML_GENERATOR_MODE=openai
LLM_BASE_URL=http://llm:8002
LLM_MODEL=adilet-generator
LLM_API_KEY=
```

If `ADILET_ML_GENERATOR_MODE` is omitted, `/generate` returns a deterministic extractive fallback
answer with valid `[n]` citations. This keeps the backend walking skeleton alive without a local LLM.

## Compose Snippet

Backend owns `docker-compose.yml`; paste this there when wiring the real stack:

```yaml
  ml-service:
    build:
      context: ./ml
      dockerfile: serving/Dockerfile
    environment:
      MODEL_MANIFEST_PATH: /app/models/model_manifest.json
      MODEL_CACHE_DIR: /models
      ADILET_ML_EMBEDDER_BACKEND: hash
      ADILET_ML_GENERATOR_MODE: fallback
      LLM_BASE_URL: http://llm:8002
      LLM_MODEL: adilet-generator
      LLM_API_KEY: ${LLM_API_KEY:-}
    volumes:
      - ./ml/models:/app/models:ro
      - ml-model-cache:/models
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health').read()"]
      interval: 10s
      timeout: 5s
      retries: 6

  llm:
    image: ghcr.io/ggerganov/llama.cpp:server
    profiles: ["llm"]
    command: ["-m", "/models/adilet-generator.gguf", "--host", "0.0.0.0", "--port", "8002"]
    volumes:
      - ./ml/models:/models:ro
    ports:
      - "8002:8002"
```
