"""Model-independent ranking and paired inference for research experiments."""

import numpy as np

from adilet_ml.eval.metrics import ndcg_at_k


def article_ranking(scores, chunks, language, limit=50):
    positions = [i for i, c in enumerate(chunks) if c["lang"] == language]
    ordered = sorted(positions, key=lambda i: (-float(scores[i]), chunks[i]["chunk_id"]))
    result = []
    seen = set()
    for i in ordered:
        article = chunks[i]["article_id"]
        if article not in seen:
            result.append(article)
            seen.add(article)
        if len(result) == limit:
            break
    return result


def bootstrap_delta(labels, baseline, challenger, seed=42):
    ids = sorted(labels)
    delta = np.asarray(
        [ndcg_at_k({q: labels[q]}, challenger) - ndcg_at_k({q: labels[q]}, baseline) for q in ids]
    )
    rng = np.random.default_rng(seed)
    clusters = {}
    for i, query in enumerate(ids):
        article = sorted(labels[query])[0]
        parts = article.split(":")
        family = (
            parts[0] + ":" + parts[2] if len(parts) == 3 and parts[1] in {"ru", "kk"} else query
        )
        clusters.setdefault(family, []).append(i)
    members = list(clusters.values())
    means = np.asarray(
        [
            delta[
                np.concatenate([members[i] for i in rng.integers(0, len(members), len(members))])
            ].mean()
            for _ in range(2000)
        ]
    )
    return {"mean": float(delta.mean()), "ci95": np.quantile(means, [0.025, 0.975]).tolist()}
