# syntax=docker/dockerfile:1.7
# ml-service with the real multilingual E5 embedder (zero-shot), for the demo stack.
#
# ML's own image (ml/serving/Dockerfile) installs only the base package, so the
# ADILET_ML_EMBEDDER_BACKEND=sentence-transformers switch has nothing to load. This overlay adds the
# `models` extras (CPU-only torch) on top of ML's image without touching ML's files, and derives a
# manifest whose pipeline_version / index_compat_id say "E5", so the backend refuses to search an
# index that was built with the hash embedder (it answers 503 "reindex required" until reindexed).
#
# Build ML's image first:  docker compose --profile ml build ml-service
# then:                    docker compose --profile ml-e5 up -d --build
ARG BASE_IMAGE=adilet-ml-service:dev
FROM ${BASE_IMAGE}

USER root
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.14.1+cpu" \
    && pip install --no-cache-dir "sentence-transformers==6.1.0" "transformers==5.19.0"

# Derive the E5 manifest from ML's manifest (no copy that could drift from ML's file).
RUN python - <<'EOF'
import json, pathlib
path = pathlib.Path("/app/models/model_manifest.json")
manifest = json.loads(path.read_text(encoding="utf-8"))
base_compat = manifest["index_compat_id"].split("-", 1)[-1]  # "hash-bm25-ch1" -> "bm25-ch1"
manifest["pipeline_version"] = manifest["pipeline_version"] + "-e5"
manifest["index_compat_id"] = "e5base-" + base_compat
manifest["embedder"]["id"] = "multilingual-e5-base-zs"
manifest["embedder"]["runtime"] = "sentence-transformers (cpu)"
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("manifest:", manifest["pipeline_version"], manifest["index_compat_id"])
EOF

USER appuser
ENV ADILET_ML_EMBEDDER_BACKEND=sentence-transformers \
    HF_HOME=/models/hf
