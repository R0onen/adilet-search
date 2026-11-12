# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12.24 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/models \
    HF_HOME=/models/hf \
    MODEL_MANIFEST_PATH=/app/models/model_manifest.json \
    MODEL_PROMPT_PATH=/app/prompts/answer_v1.md

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

# CPU by default; the optional GPU overlay selects the pinned CUDA wheel explicitly.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_VERSION=2.14.1+cpu
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url "${TORCH_INDEX_URL}" "torch==${TORCH_VERSION}"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY models ./models
COPY prompts ./prompts
ARG ML_EXTRAS=models

RUN --mount=type=cache,target=/root/.cache/pip \
    case ",${ML_EXTRAS}," in \
         *,research,*) pip install --no-deps --index-url "${TORCH_INDEX_URL}" "torchvision==0.29.1" ;; \
         *) true ;; \
       esac \
    && uv export --frozen --extra models --extra research --no-dev --no-emit-project --no-hashes \
        --no-annotate --output-file /tmp/constraints.txt \
    && pip install --constraint /tmp/constraints.txt ".[${ML_EXTRAS}]" \
    && mkdir -p /models \
    && chown -R appuser:appuser /models /app

USER appuser
EXPOSE 8001
# Model weights (E5 ~1.1 GB, reranker ~0.5 GB) download here on the first start.
VOLUME ["/models"]

HEALTHCHECK --interval=15s --timeout=10s --retries=20 --start-period=300s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health').read()"

CMD ["uvicorn", "adilet_ml.serving.app:app", "--host", "0.0.0.0", "--port", "8001"]
