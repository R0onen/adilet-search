"""Fine-tune the reranker on written questions about all 40 acts of the deployed corpus.

    python ml/scripts/train_reranker.py [--out ml/models/checkpoints/reranker-ft-40acts]

Assignment 4 (configuration E3b) trained the reranker on LLM-written questions about the 8 main
codes only. The deployed index holds 32 more acts. This script repeats E3b with the same model,
input format, learning rate, batch, negatives and epoch selection, and adds the training questions
of `data/eval/synthetic_t2/` (acts outside the 8 codes). Candidates come from BM25 over the
40-act corpus, as in the product.

Evaluation, written to `ml/experiments/reranker-40acts/results.json`:
- the 195 synthetic test questions of Assignment 4, with candidates from BM25 over the 8 codes
  exactly as in the notebook, for the new model and for the E3b checkpoint, with a paired
  bootstrap interval and a randomisation test;
- the 55 everyday questions of `data/eval/everyday/` (articles excluded from training), with
  candidates from BM25 over the 40 acts; any of the labelled articles counts.

Needs a GPU for a reasonable run time (about 6 minutes on an 8 GB card) and the packages of the
notebooks: torch, transformers, bm25s, PyStemmer, pandas, pyarrow, and `adilet-ml` installed.
"""

from __future__ import annotations

import os

# bm25s runs a JAX operation on import, and JAX would then reserve most of the GPU.
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("USE_TF", "0")

import argparse
import gc
import json
import math
import random
import time
from pathlib import Path

import bm25s
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

from adilet_ml.retrieval.sparse import tokenize

REPO = Path(__file__).resolve().parents[2]
SEED = 42
CE_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MAX_LEN, LR, BATCH, MAX_EPOCHS = 320, 1e-5, 32, 4
K_CAND, N_NEG = 20, 7
BM25_PARAMS = {"ru": (1.2, 0.9), "kk": (2.0, 0.9)}  # tuned on validation in Assignment 4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)


def read_jsonl(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    return pd.DataFrame([json.loads(line) for line in lines if line])


def load_corpus(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Articles per language with the text the reranker reads (as in the A4 notebook)."""
    columns = ["article_id", "lang", "chunk_index", "text", "unit_title", "doc_short_title"]
    chunks = pd.read_parquet(data_dir / "chunks.parquet", columns=columns)
    articles = (
        chunks.sort_values(["article_id", "chunk_index"])
        .groupby("article_id", sort=False)
        .agg(lang=("lang", "first"), body=("text", "\n".join), doc=("doc_short_title", "first"))
        .reset_index()
    )
    articles["passage"] = articles["doc"] + ". " + articles["body"].str.slice(0, 2000)
    return {lang: g.reset_index(drop=True) for lang, g in articles.groupby("lang")}


class Candidates:
    """Top-20 BM25 candidates over one corpus, with the tuned parameters per language."""

    def __init__(self, corpus: dict[str, pd.DataFrame]):
        self.corpus = corpus
        self.index = {}
        for lang, frame in corpus.items():
            k1, b = BM25_PARAMS[lang]
            index = bm25s.BM25(k1=k1, b=b)
            index.index([tokenize(t, lang) for t in frame["body"]], show_progress=False)
            self.index[lang] = index
        self.position = {
            lang: {a: i for i, a in enumerate(f["article_id"])} for lang, f in corpus.items()
        }

    def retrieve(self, lang: str, texts: list[str]) -> np.ndarray:
        docs, _ = self.index[lang].retrieve(
            [tokenize(t, lang) for t in texts],
            k=K_CAND,
            show_progress=False,
            backend_selection="numpy",
        )
        return docs

    def pairs(self, questions: pd.DataFrame, n_neg: int | None) -> pd.DataFrame:
        """(question, article) pairs. With `n_neg`, the correct article plus `n_neg` negatives drawn
        at random from the candidates (the article is added when BM25 missed it); without it, all
        20 candidates. `relevant` is a list of article ids per question."""
        rows, rng = [], np.random.default_rng(SEED)
        for lang in ("ru", "kk"):
            part = questions[questions["lang"] == lang]
            if part.empty:
                continue
            ids = self.corpus[lang]["article_id"].to_numpy()
            docs = self.retrieve(lang, part["text"].tolist())
            for (_, q), cand in zip(part.iterrows(), docs, strict=True):
                labels = np.isin(ids[cand], q["relevant"])
                keep = np.ones(len(cand), dtype=bool)
                if n_neg is not None:
                    negatives = np.flatnonzero(~labels)
                    keep = labels.copy()
                    chosen = rng.choice(negatives, size=min(n_neg, len(negatives)), replace=False)
                    keep[chosen] = True
                for rank, doc in enumerate(cand):
                    if keep[rank]:
                        rows.append((q["query_id"], q["text"], lang, int(doc), int(labels[rank])))
                if n_neg is not None and not labels.any():
                    doc = self.position[lang][q["relevant"][0]]
                    rows.append((q["query_id"], q["text"], lang, doc, 1))
        pairs = pd.DataFrame(rows, columns=["query_id", "query", "lang", "doc", "label"])
        pairs["passage"] = [
            self.corpus[lang]["passage"].iat[d]
            for lang, d in zip(pairs["lang"], pairs["doc"], strict=True)
        ]
        return pairs


class PairDataset(Dataset):
    def __init__(self, pairs: pd.DataFrame, tokenizer):
        self.encoded = tokenizer(
            pairs["query"].tolist(),
            pairs["passage"].tolist(),
            truncation="only_second",
            max_length=MAX_LEN,
        )
        self.labels = pairs["label"].astype("float32").to_numpy()

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, i: int) -> dict:
        return {**{k: v[i] for k, v in self.encoded.items()}, "labels": self.labels[i]}


class BCETrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(
            outputs.logits.view(-1), labels.float().view(-1)
        )
        return (loss, outputs) if return_outputs else loss


@torch.inference_mode()
def score(model, tokenizer, pairs: pd.DataFrame, batch: int = 64) -> np.ndarray:
    model.eval()
    out = []
    for start in range(0, len(pairs), batch):
        part = pairs.iloc[start : start + batch]
        encoded = tokenizer(
            part["query"].tolist(),
            part["passage"].tolist(),
            truncation="only_second",
            max_length=MAX_LEN,
            padding=True,
            return_tensors="pt",
        ).to(DEVICE)
        with torch.autocast("cuda", enabled=DEVICE == "cuda"):
            logits = model(**encoded).logits.view(-1)
        out.append(logits.float().cpu().numpy())
    return np.concatenate(out)


def ranks_of(pairs: pd.DataFrame, scores: np.ndarray) -> pd.Series:
    """Rank of the first relevant article per question (inf: not among the candidates)."""
    frame = pairs.assign(score=scores).sort_values(["query_id", "score"], ascending=[True, False])
    frame["rank"] = frame.groupby("query_id").cumcount() + 1
    first = frame[frame["label"] == 1].groupby("query_id")["rank"].min()
    return first.reindex(pairs["query_id"].unique()).fillna(np.inf).astype(float)


def metrics(ranks: pd.Series) -> dict[str, float]:
    r = ranks.to_numpy()
    hit = r <= 10
    return {
        "hit@1": round(float((r == 1).mean()), 4),
        "mrr@10": round(float(np.where(hit, 1 / r, 0).mean()), 4),
        "ndcg@10": round(float(np.where(hit, 1 / np.log2(r + 1), 0).mean()), 4),
        "recall@10": round(float(hit.mean()), 4),
    }


def paired(base: pd.Series, new: pd.Series, n: int = 10_000) -> dict[str, float | int]:
    gain = lambda r: np.where(r <= 10, 1 / np.log2(r + 1), 0.0)  # noqa: E731
    d = gain(new.to_numpy()) - gain(base.loc[new.index].to_numpy())
    rng = np.random.default_rng(SEED)
    boot = rng.choice(d, (n, len(d))).mean(1)
    flipped = (rng.choice([-1.0, 1.0], (n, len(d))) * d).mean(1)
    return {
        "mean_ndcg10_difference": round(float(d.mean()), 4),
        "ci95": [
            round(float(np.quantile(boot, 0.025)), 4),
            round(float(np.quantile(boot, 0.975)), 4),
        ],
        "p_value": round(float((np.abs(flipped) >= abs(d.mean()) - 1e-12).mean()), 4),
        "better": int((d > 0).sum()),
        "worse": int((d < 0).sum()),
    }


def train(
    train_pairs: pd.DataFrame, val_pairs: pd.DataFrame, tokenizer, out: Path, epochs: int
) -> list[dict]:
    seed_everything()
    dataset = PairDataset(train_pairs, tokenizer)
    collator = DataCollatorWithPadding(tokenizer)
    model = AutoModelForSequenceClassification.from_pretrained(CE_NAME).to(DEVICE)
    history, best = [], -1.0
    steps = math.ceil(len(train_pairs) / BATCH)
    for epoch in range(1, epochs + 1):
        # One Trainer per epoch, as in the notebook (the warm-up restarts each epoch).
        args = TrainingArguments(
            output_dir=str(out.parent / f"runs-{out.name}"),
            learning_rate=LR,
            num_train_epochs=1,
            per_device_train_batch_size=BATCH,
            warmup_steps=int(0.1 * steps),
            weight_decay=0.01,
            fp16=DEVICE == "cuda",
            seed=SEED,
            logging_steps=50,
            save_strategy="no",
            report_to="none",
            disable_tqdm=True,
        )
        BCETrainer(model=model, args=args, train_dataset=dataset, data_collator=collator).train()
        val = metrics(ranks_of(val_pairs, score(model, tokenizer, val_pairs)))
        history.append({"epoch": epoch, **{f"val_{k}": v for k, v in val.items()}})
        print(history[-1], flush=True)
        if val["ndcg@10"] > best:
            best = val["ndcg@10"]
            model.save_pretrained(str(out))
            tokenizer.save_pretrained(str(out))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return history


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--out", type=Path, default=REPO / "ml/models/checkpoints/reranker-ft-40acts"
    )
    parser.add_argument(
        "--baseline", type=Path, default=REPO / "ml/models/checkpoints/reranker-ft-written"
    )
    parser.add_argument("--report", type=Path, default=REPO / "ml/experiments/reranker-40acts")
    parser.add_argument("--t2-dir", type=Path, default=REPO / "data/eval/synthetic_t2")
    parser.add_argument("--epochs", type=int, default=MAX_EPOCHS)
    args = parser.parse_args()
    seed_everything()
    started = time.time()

    corpus8 = load_corpus(REPO / "data/processed")
    corpus40 = load_corpus(REPO / "data/processed_t2")
    bm8, bm40 = Candidates(corpus8), Candidates(corpus40)

    synthetic = read_jsonl(REPO / "data/eval/synthetic/queries.jsonl").merge(
        read_jsonl(REPO / "data/eval/synthetic/qrels.jsonl"), on="query_id"
    )
    t2 = read_jsonl(args.t2_dir / "queries.jsonl").merge(
        read_jsonl(args.t2_dir / "qrels.jsonl"), on="query_id"
    )
    for frame in (synthetic, t2):
        frame["relevant"] = frame["article_id"].map(lambda a: [a])
    everyday = read_jsonl(REPO / "data/eval/everyday/queries.jsonl")

    # Leakage checks: no article in two splits, no everyday article in training.
    unit = lambda ids: {a.replace(":ru:", ":").replace(":kk:", ":") for a in ids}  # noqa: E731
    train_units = unit(synthetic[synthetic.split == "train"].article_id) | unit(
        t2[t2.split == "train"].article_id
    )
    held_units = unit(synthetic[synthetic.split != "train"].article_id) | unit(
        t2[t2.split == "val"].article_id
    )
    everyday_units = unit(a for ids in everyday["relevant"] for a in ids)
    if train_units & held_units:
        raise SystemExit("an article is in training and in validation or test")
    if train_units & everyday_units:
        raise SystemExit("an everyday article is in training")

    train_q = pd.concat([synthetic[synthetic.split == "train"], t2[t2.split == "train"]])
    val_q = pd.concat([synthetic[synthetic.split == "val"], t2[t2.split == "val"]])
    train_pairs = bm40.pairs(train_q, N_NEG)
    val_pairs = bm40.pairs(val_q, None)
    test8 = bm8.pairs(synthetic[synthetic.split == "test"], None)
    test_everyday = bm40.pairs(everyday, None)
    print(
        f"train {len(train_pairs):,} pairs from {train_q.query_id.nunique()} questions "
        f"({(train_q.query_id.str.startswith('t')).sum()} about the added acts); "
        f"val {val_q.query_id.nunique()} questions; device {DEVICE}",
        flush=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(CE_NAME)
    history = train(train_pairs, val_pairs, tokenizer, args.out, args.epochs)
    minutes = (time.time() - started) / 60

    results: dict = {"data": {}, "models": {}, "history": history, "minutes": round(minutes, 1)}
    results["data"] = {
        "train_pairs": len(train_pairs),
        "train_questions": int(train_q.query_id.nunique()),
        "train_questions_added_acts": int(train_q.query_id.str.startswith("t").sum()),
        "val_questions": int(val_q.query_id.nunique()),
        "test8_questions": int(test8.query_id.nunique()),
        "everyday_questions": int(test_everyday.query_id.nunique()),
        # share of everyday questions with a labelled article among the 20 BM25 candidates
        "everyday_ceiling": round(
            float(test_everyday.groupby("query_id")["label"].max().mean()), 4
        ),
        "test8_ceiling": round(float(test8.groupby("query_id")["label"].max().mean()), 4),
    }
    lang_of = {lang: list(g.query_id) for lang, g in everyday.groupby("lang")}
    ranks = {}
    for name, path in (("E3b (8 codes)", args.baseline), ("new (40 acts)", args.out)):
        model = AutoModelForSequenceClassification.from_pretrained(str(path)).to(DEVICE)
        ranks[name] = {
            "test8": ranks_of(test8, score(model, tokenizer, test8)),
            "everyday": ranks_of(test_everyday, score(model, tokenizer, test_everyday)),
        }
        results["models"][name] = {
            "test8": metrics(ranks[name]["test8"]),
            "everyday": metrics(ranks[name]["everyday"]),
            **{
                f"everyday_{lang}": metrics(ranks[name]["everyday"].loc[lang_of[lang]])
                for lang in ("ru", "kk")
            },
        }
        del model
        torch.cuda.empty_cache()
    base, new = ranks["E3b (8 codes)"], ranks["new (40 acts)"]
    results["paired"] = {
        "test8": paired(base["test8"], new["test8"]),
        "everyday": paired(base["everyday"], new["everyday"]),
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
