"""Write plain-language questions for a sample of articles with an LLM (synthetic queries).

    python ml/scripts/build_synthetic_eval.py [--articles 400] [--model openai/gpt-oss-120b]

Title queries (build_title_eval.py) use the legislator's own words. Real users do not, so this
script asks an LLM for two queries per sampled article, in the article's language:
- `plain`: how a person without legal training would ask;
- `term`: a short query in legal terminology.
Neither may copy the title or mention the article number. The article is the relevant document (3).

The sample is stratified by split and language over the same article groups as
`data/eval/splits.json`, so a synthetic query is always in the same subset as its article's title
query. Output: `data/eval/synthetic/{queries,qrels}.jsonl` and `meta.json`. The run is resumable:
articles that already have queries are skipped.

Numbers computed on this set must be reported as "synthetic queries (LLM-written)". The LLM reads
the article while writing, so some wording leaks from the text; human questions remain the
stronger test.

Needs an OpenAI-compatible endpoint: `LLM_BASE_URL` (without /v1) and `LLM_API_KEY`, from the
environment or the repository's `.env`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = "synthetic_queries_v2"
MAX_ARTICLE_CHARS = 1500
SPLIT_SHARE = {"train": 0.60, "val": 0.15, "test": 0.25}
LANG_SHARE = {"ru": 0.6, "kk": 0.4}

SYSTEM = """You write search queries for testing a legal search system over the legislation of \
Kazakhstan. You get one article. Write two queries that this article answers, in the SAME \
language as the article ({language}):
- "plain": a question in everyday words, as a person without legal training would ask it. \
Describe the life situation; avoid the statute's own terms where a common word exists.
- "term": a short query in legal terminology, as a lawyer would type it.
Rules: 4 to 25 words each. Do not copy the article title. Do not mention the article number or \
the name of the code. Use only facts that are in the article. \
Return only JSON: {{"plain": "...", "term": "..."}}"""


class DailyLimitError(Exception):
    """The provider's per-day limit for the model was reached."""


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip())
    return env


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sample_articles(data_dir: Path, eval_dir: Path, total: int, seed: int) -> list[dict[str, Any]]:
    """Articles with a title query, stratified by split and language."""
    queries = {q["query_id"]: q for q in read_jsonl(eval_dir / "queries.jsonl")}
    article_of = {r["query_id"]: r["article_id"] for r in read_jsonl(eval_dir / "qrels.jsonl")}
    splits = json.loads((eval_dir / "splits.json").read_text(encoding="utf-8"))["query_splits"]

    columns = ["article_id", "chunk_index", "text", "unit_title", "doc_short_title"]
    chunks = pq.read_table(data_dir / "chunks.parquet", columns=columns).to_pylist()
    first_chunk = {c["article_id"]: c for c in chunks if c["chunk_index"] == 0}

    picked: list[dict[str, Any]] = []
    rng = random.Random(seed)  # noqa: S311 - reproducible sample
    for split, split_share in SPLIT_SHARE.items():
        for lang, lang_share in LANG_SHARE.items():
            pool = sorted(article_of[qid] for qid in splits[split] if queries[qid]["lang"] == lang)
            rng.shuffle(pool)
            for article_id in pool[: round(total * split_share * lang_share)]:
                chunk = first_chunk[article_id]
                picked.append(
                    {
                        "article_id": article_id,
                        "lang": lang,
                        "split": split,
                        "title": chunk["unit_title"],
                        "doc": chunk["doc_short_title"],
                        "text": chunk["text"][:MAX_ARTICLE_CHARS],
                    }
                )
    return picked


def ask(client: httpx.Client, url: str, model: str, article: dict[str, Any]) -> dict[str, str]:
    language = "Kazakh" if article["lang"] == "kk" else "Russian"
    payload = {
        "model": model,
        "temperature": 0.7,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM.format(language=language)},
            {"role": "user", "content": f"Title: {article['title']}\n\n{article['text']}"},
        ],
    }
    if "gpt-oss" in model:
        # Reasoning models spend most of their tokens thinking; this task does not need it.
        payload["reasoning_effort"] = "low"
    attempts = 0
    while attempts < 6:
        try:
            response = client.post(url, json=payload)
        except httpx.HTTPError:  # a dropped connection or a timeout: wait and try again
            attempts += 1
            time.sleep(10)
            continue
        if response.status_code == 429 and "per day" in response.text:
            # The daily token budget of this model is used up. The run is resumable: rerun
            # later, or with another --model.
            raise DailyLimitError(response.json()["error"]["message"].split(". Please")[0])
        if response.status_code == 429:
            # The per-minute budget: wait as long as the server asks. Not counted as a failure.
            time.sleep(min(float(response.headers.get("retry-after", "20")) + 1, 120))
            continue
        attempts += 1
        if response.status_code >= 500:
            time.sleep(15)
            continue
        if response.status_code == 400:  # the model's output failed the endpoint's JSON check
            time.sleep(2)
            continue
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"] or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        try:
            data = json.loads(match.group(0)) if match else {}
        except json.JSONDecodeError:
            data = {}
        if isinstance(data.get("plain"), str) and isinstance(data.get("term"), str):
            return {"plain": data["plain"].strip(), "term": data["term"].strip()}
    return {}


def acceptable(text: str, article: dict[str, Any]) -> bool:
    words = text.split()
    title = (article["title"] or "").strip().lower()
    return 3 <= len(words) <= 30 and text.strip().lower().rstrip("?.") != title.rstrip("?.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data/processed")
    parser.add_argument("--eval-dir", type=Path, default=REPO_ROOT / "data/eval")
    parser.add_argument("--articles", type=int, default=400)
    parser.add_argument("--model", default="openai/gpt-oss-120b")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pause", type=float, default=5.5, help="seconds between requests")
    args = parser.parse_args(argv)

    env = load_env()
    if not env.get("LLM_API_KEY") or not env.get("LLM_BASE_URL"):
        raise SystemExit("LLM_BASE_URL and LLM_API_KEY are required (environment or .env)")
    url = env["LLM_BASE_URL"].rstrip("/") + "/v1/chat/completions"

    out_dir = args.eval_dir / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)
    queries_path, qrels_path = out_dir / "queries.jsonl", out_dir / "qrels.jsonl"
    done = {r["article_id"] for r in read_jsonl(qrels_path)}
    counter = len(read_jsonl(queries_path))

    articles = sample_articles(args.data_dir, args.eval_dir, args.articles, args.seed)
    todo = [a for a in articles if a["article_id"] not in done]
    print(f"{len(articles)} sampled, {len(done)} done, {len(todo)} to go", flush=True)

    headers = {"Authorization": "Bearer " + env["LLM_API_KEY"]}
    with (
        httpx.Client(headers=headers, timeout=httpx.Timeout(45, connect=10)) as client,
        queries_path.open("a", encoding="utf-8", newline="\n") as queries_file,
        qrels_path.open("a", encoding="utf-8", newline="\n") as qrels_file,
    ):
        for number, article in enumerate(todo, 1):
            try:
                answer = ask(client, url, args.model, article)
            except DailyLimitError as limit:
                print(f"stopped after {number - 1} articles: {limit}", flush=True)
                break
            if not answer:
                print(f"no usable answer for {article['article_id']}; skipped", flush=True)
            for query_type in ("plain", "term"):
                text = answer.get(query_type, "")
                if not acceptable(text, article):
                    continue
                counter += 1
                query_id = f"s{counter:05d}"
                query = {
                    "query_id": query_id,
                    "text": text,
                    "lang": article["lang"],
                    "source": "synthetic",
                    "query_type": query_type,
                    "split": article["split"],
                    "answerable": True,
                }
                qrel = {"query_id": query_id, "article_id": article["article_id"], "relevance": 3}
                queries_file.write(json.dumps(query, ensure_ascii=False) + "\n")
                qrels_file.write(json.dumps(qrel, ensure_ascii=False) + "\n")
            queries_file.flush()
            qrels_file.flush()
            if number % 25 == 0:
                print(f"{number}/{len(todo)} articles, {counter} queries", flush=True)
            time.sleep(args.pause)

    queries = read_jsonl(queries_path)
    meta_path = out_dir / "meta.json"
    previous_models = (
        json.loads(meta_path.read_text(encoding="utf-8")).get("models", [])
        if meta_path.exists()
        else []
    )
    done_articles = {r["article_id"] for r in read_jsonl(qrels_path)}
    meta = {
        "prompt_version": PROMPT_VERSION,
        "models": sorted(set(previous_models) | {args.model}),
        "seed": args.seed,
        "articles_sampled": len(articles),
        "articles_done": len(done_articles & {a["article_id"] for a in articles}),
        "queries": len(queries),
        "by_split_lang_type": {
            f"{split}/{lang}/{kind}": sum(
                q["split"] == split and q["lang"] == lang and q["query_type"] == kind
                for q in queries
            )
            for split in SPLIT_SHARE
            for lang in LANG_SHARE
            for kind in ("plain", "term")
        },
        "notes": "LLM-written queries; the source article is the only labelled relevant document.",
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"done: {len(queries)} queries in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
