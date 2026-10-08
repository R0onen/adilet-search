"""Fetch and/or build a corpus from Adilet HTML into data-contract Parquet files."""

from __future__ import annotations

import argparse
from pathlib import Path

from adilet_ml.ingest.corpus import build_from_cached_html, fetch_target_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("ml/configs/corpus.yaml"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--fetch", action="store_true", help="download missing HTML before parsing")
    parser.add_argument("--limit-acts", type=int, default=None)
    parser.add_argument("--max-chunk-tokens", type=int, default=400)
    args = parser.parse_args(argv)
    if args.fetch:
        paths = fetch_target_html(args.config, args.raw_dir, args.limit_acts)
        print(f"cached {len(paths)} pages under {args.raw_dir}")
    manifest = build_from_cached_html(
        config_path=args.config,
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        limit_acts=args.limit_acts,
        max_chunk_tokens=args.max_chunk_tokens,
    )
    print(
        "wrote "
        f"{manifest['row_counts']['documents']} documents, "
        f"{manifest['row_counts']['articles']} articles, "
        f"{manifest['row_counts']['chunks']} chunks to {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
