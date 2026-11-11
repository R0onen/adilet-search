# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/models \
    HF_HOME=/models/hf \
    MODEL_MANIFEST_PATH=/app/models/model_manifest.json

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

# CPU-only torch from the PyTorch index: the default PyPI wheel bundles CUDA (several GB).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu

COPY pyproject.toml README.md ./
COPY src ./src
COPY models ./models
COPY prompts ./prompts

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".[models]" \
    && mkdir -p /models \
    && chown -R appuser:appuser /models /app

USER appuser
EXPOSE 8001
# Model weights (E5 ~1.1 GB, reranker ~0.5 GB) download here on the first start.
VOLUME ["/models"]

HEALTHCHECK --interval=15s --timeout=10s --retries=20 --start-period=300s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health').read()"

CMD ["uvicorn", "adilet_ml.serving.app:app", "--host", "0.0.0.0", "--port", "8001"]
