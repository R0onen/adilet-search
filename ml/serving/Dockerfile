FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/models \
    MODEL_MANIFEST_PATH=/app/models/model_manifest.json

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml README.md ./
COPY src ./src
COPY models ./models

RUN pip install --no-cache-dir . \
    && mkdir -p /models \
    && chown -R appuser:appuser /models /app

USER appuser
EXPOSE 8001
VOLUME ["/models"]

HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health').read()"

CMD ["uvicorn", "adilet_ml.serving.app:app", "--host", "0.0.0.0", "--port", "8001"]
