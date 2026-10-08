"""Fetch model weights into MODEL_CACHE_DIR when real backends are enabled."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", default=["intfloat/multilingual-e5-base"])
    parser.add_argument("--cache-dir", default=os.getenv("MODEL_CACHE_DIR", ".cache/models"))
    args = parser.parse_args(argv)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit("Install adilet-ml[models] before fetching model weights.") from exc

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for model in args.model:
        SentenceTransformer(model, cache_folder=str(cache_dir))
        print(f"cached {model} under {cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
