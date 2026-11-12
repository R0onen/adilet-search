"""Capture non-secret local deployment identity and health for the final report.

Run from any directory with Python. Does not print environment files or Docker env dumps.
"""

import hashlib
import json
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8").strip()


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def main() -> None:
    # Explicit whitelist: no credential-bearing fields are returned from a container.
    ml_keys = [
        "ADILET_ML_DEVICE",
        "ADILET_ML_INFERENCE_WORKERS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "ADILET_ML_GENERATOR_MODE",
        "LLM_MODEL",
    ]
    be_keys = [
        "SEARCH_RERANK_TOP_N",
        "SEARCH_EMBED_TIMEOUT_S",
        "SEARCH_RERANK_TIMEOUT_S",
    ]
    settings = {}
    for service, keys in [("ml-service", ml_keys), ("backend", be_keys)]:
        script = (
            f"import os,json; print(json.dumps({{k:os.getenv(k) for k in {keys!r}}}))"
        )
        settings[service] = json.loads(
            command(
                "docker", "exec", f"adilet-final-{service}-1", "python", "-c", script
            )
        )
    torch_info = json.loads(
        command(
            "docker",
            "exec",
            "adilet-final-ml-service-1",
            "python",
            "-c",
            "import torch,json; print(json.dumps({'torch_version':torch.__version__,"
            "'cuda_available':torch.cuda.is_available(),'gpu_name':torch.cuda.get_device_name(0) "
            "if torch.cuda.is_available() else None}))",
        )
    )
    targets = get("http://127.0.0.1:19090/api/v1/targets")["data"]["activeTargets"]
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "git_head": command("git", "rev-parse", "HEAD"),
        "git_branch": command("git", "branch", "--show-current"),
        "uncommitted_changes": bool(command("git", "status", "--porcelain")),
        "settings": settings,
        "torch": torch_info,
        "health": get("http://127.0.0.1:18000/api/v1/health"),
        "version": get("http://127.0.0.1:18000/api/v1/version"),
        "ml_health": get("http://127.0.0.1:18001/health"),
        "qdrant": get("http://127.0.0.1:16333/collections/legal_chunks")["result"],
        "monitoring": [
            {"job": t["labels"]["job"], "health": t["health"]} for t in targets
        ],
        "image_ids": {
            s: command(
                "docker", "inspect", "--format", "{{.Image}}", f"adilet-final-{s}-1"
            )
            for s in ["backend", "ml-service", "frontend", "prometheus", "grafana"]
        },
        "file_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in [
                "ml/models/model_manifest.json",
                "ml/uv.lock",
                "backend/uv.lock",
                "frontend/package-lock.json",
            ]
        },
    }
    # Qdrant configuration contains no documents or queries; keep the evidence small.
    result["qdrant"] = {
        k: result["qdrant"].get(k)
        for k in ["status", "points_count", "indexed_vectors_count"]
    }
    output = ROOT / "docs/report/final_runtime.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved non-secret runtime identity: {output}")


if __name__ == "__main__":
    main()
