"""Download the corpus source and build the `contracts/data_schema.md` Parquet files.

    python ml/scripts/download_data.py [--out data/processed] [--all-acts]

The source is AdiletCodex v1.0 (CC BY 4.0, https://doi.org/10.5281/zenodo.22812626): the official
texts of the codes and laws of Kazakhstan parsed from adilet.zan.kz. It is public, so this works on
a fresh machine or Colab runtime without tokens. The file is cached in `data/raw/adiletcodex/` and
verified by MD5 before use.
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

from adilet_ml.ingest import adiletcodex

DATA_URL = "https://zenodo.org/api/records/22812626/files/adiletcodex.csv.gz/content"
DATA_MD5 = "bde74683987a1e52c16d339ba14953a6"
REPO_ROOT = Path(__file__).resolve().parents[2]


def fetch(raw_path: Path) -> Path:
    """Download once; a cached file with the right checksum is reused."""
    if not raw_path.exists() or _md5(raw_path) != DATA_MD5:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {DATA_URL}")
        urllib.request.urlretrieve(DATA_URL, raw_path)
    digest = _md5(raw_path)
    if digest != DATA_MD5:
        raise SystemExit(f"{raw_path}: MD5 {digest}, expected {DATA_MD5}; delete it and retry")
    return raw_path


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324 - integrity, not security


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--raw", type=Path, default=REPO_ROOT / "data/raw/adiletcodex/adiletcodex.csv.gz"
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data/processed")
    parser.add_argument("--all-acts", action="store_true", help="every act, not only Tier-1")
    parser.add_argument("--docs", nargs="+", metavar="DOC_ID", help="only these Tier-1 acts")
    args = parser.parse_args(argv)

    importer_args = ["--csv", str(fetch(args.raw)), "--out", str(args.out)]
    if args.all_acts:
        importer_args.append("--all-acts")
    if args.docs:
        importer_args += ["--docs", *args.docs]
    return adiletcodex.main(importer_args)


if __name__ == "__main__":
    raise SystemExit(main())
