"""LLM-written training questions for the acts of the second corpus tier (outside the 8 codes).

    python ml/scripts/build_synthetic_t2.py [--articles 320]

The reranker of pipeline 1.0.0 was trained on questions about the 8 main codes only. This script
writes questions for a sample of articles of the other acts in `data/processed_t2`, with the same
prompt and checks as `build_synthetic_eval.py`. Output: `data/eval/synthetic_t2/` (queries, qrels,
meta), split by article into train (85%) and val (15%). There is no test split: the test for
these acts is `data/eval/everyday/`, and every article labelled there (in both languages) is
excluded from the sample, so that set stays unseen.

Resumable; switches to the next model when a model's daily limit is reached.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import yaml
from build_synthetic_eval import (
    MAX_ARTICLE_CHARS,
    PROMPT_VERSION,
    DailyLimitError,
    acceptable,
    ask,
    load_env,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "data/eval/synthetic_t2"
MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "openai/gpt-oss-safeguard-20b"]
LANG_SHARE = {"ru": 0.6, "kk": 0.4}
MIN_ARTICLE_CHARS = 200


def group_of(article_id: str) -> str:
    doc, _lang, key = article_id.split(":")
    return f"{doc}:{key}"


def sample(data_dir: Path, total: int, seed: int) -> list[dict]:
    config = yaml.safe_load((REPO_ROOT / "ml/configs/corpus.yaml").read_text(encoding="utf-8"))
    tier1 = {
        act["doc_id"]
        for value in config.values()
        if isinstance(value, list)
        for act in value
        if isinstance(act, dict) and act.get("tier") == 1
    }
    everyday = REPO_ROOT / "data/eval/everyday/queries.jsonl"
    held_out = {
        group_of(article_id)
        for line in everyday.read_text(encoding="utf-8").splitlines()
        for article_id in json.loads(line)["relevant"]
    }
    columns = ["article_id", "chunk_index", "text", "unit_title", "doc_short_title"]
    chunks = pq.read_table(data_dir / "chunks.parquet", columns=columns).to_pylist()
    pool: dict[str, list[dict]] = {"ru": [], "kk": []}
    for chunk in chunks:
        doc, lang, _key = chunk["article_id"].split(":")
        if (
            chunk["chunk_index"] == 0
            and doc not in tier1
            and group_of(chunk["article_id"]) not in held_out
            and len(chunk["text"]) >= MIN_ARTICLE_CHARS
        ):
            pool[lang].append(chunk)
    rng = random.Random(seed)  # noqa: S311 - reproducible sample
    picked = []
    for lang, share in LANG_SHARE.items():
        items = sorted(pool[lang], key=lambda c: c["article_id"])
        rng.shuffle(items)
        for chunk in items[: round(total * share)]:
            digest = hashlib.sha256(group_of(chunk["article_id"]).encode()).digest()[0]
            picked.append(
                {
                    "article_id": chunk["article_id"],
                    "lang": lang,
                    "split": "val" if digest < 0.15 * 256 else "train",
                    "title": chunk["unit_title"],
                    "doc": chunk["doc_short_title"],
                    "text": chunk["text"][:MAX_ARTICLE_CHARS],
                }
            )
    return picked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data/processed_t2")
    parser.add_argument("--articles", type=int, default=320)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pause", type=float, default=4.0)
    args = parser.parse_args()

    env = load_env()
    url = env["LLM_BASE_URL"].rstrip("/") + "/v1/chat/completions"
    OUT.mkdir(parents=True, exist_ok=True)
    queries_path, qrels_path = OUT / "queries.jsonl", OUT / "qrels.jsonl"
    done = set()
    if qrels_path.exists():
        done = {
            json.loads(line)["article_id"] for line in qrels_path.read_text("utf-8").splitlines()
        }
    count = 0  # continue after the highest id, so that an id is never reused
    if queries_path.exists():
        lines = queries_path.read_text("utf-8").splitlines()
        count = max((int(json.loads(line)["query_id"][1:]) for line in lines), default=0)

    articles = [
        a for a in sample(args.data_dir, args.articles, args.seed) if a["article_id"] not in done
    ]
    models = list(MODELS)
    headers = {"Authorization": f"Bearer {env['LLM_API_KEY']}"}
    with (
        httpx.Client(timeout=90, headers=headers) as client,
        queries_path.open("a", encoding="utf-8", newline="\n") as queries,
        qrels_path.open("a", encoding="utf-8", newline="\n") as qrels,
    ):
        for index, article in enumerate(articles, 1):
            written: dict[str, str] = {}
            while models:
                try:
                    written = ask(client, url, models[0], article)
                    break
                except DailyLimitError as exc:
                    print(f"{models[0]}: {exc}", flush=True)
                    models.pop(0)
            if not models:
                print("every model reached its daily limit; rerun later", flush=True)
                break
            for query_type, text in written.items():
                if not acceptable(text, article):
                    continue
                count += 1
                query_id = f"t{count:05d}"
                row = {
                    "query_id": query_id,
                    "text": text,
                    "lang": article["lang"],
                    "source": "synthetic",
                    "query_type": query_type,
                    "split": article["split"],
                    "answerable": True,
                }
                queries.write(json.dumps(row, ensure_ascii=False) + "\n")
                qrels.write(
                    json.dumps(
                        {"query_id": query_id, "article_id": article["article_id"], "relevance": 3}
                    )
                    + "\n"
                )
            queries.flush()
            qrels.flush()
            if index % 20 == 0:
                print(f"{index}/{len(articles)} articles, {count} queries", flush=True)
            time.sleep(args.pause)

    rows = [json.loads(line) for line in queries_path.read_text("utf-8").splitlines()]
    meta = {
        "prompt_version": PROMPT_VERSION,
        "models": MODELS,
        "seed": args.seed,
        "articles_sampled": args.articles,
        "queries": len(rows),
        "by_split_lang": {
            f"{split}/{lang}": sum(r["split"] == split and r["lang"] == lang for r in rows)
            for split in ("train", "val")
            for lang in ("ru", "kk")
        },
        "notes": "LLM-written queries for acts outside the 8 codes; the source article is the "
        "only labelled relevant document. Articles of data/eval/everyday are excluded.",
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
