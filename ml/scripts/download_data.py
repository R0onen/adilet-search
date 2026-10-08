"""Placeholder downloader for the future private Hugging Face dataset release."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-version", required=True)
    parser.parse_args(argv)
    raise SystemExit(
        "HF dataset download is not configured yet. Build the bootstrap sample with "
        "`python -m adilet_ml.data.sample_builder --out data/sample`."
    )


if __name__ == "__main__":
    raise SystemExit(main())
