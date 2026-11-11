# ML technical notes

- Package and service: `ml/README.md`, `ml/serving/README.md`.
- Interface to the backend: `contracts/ml_service.md` (the manifest schema is §3).
- Current pipeline and its limits: `ml/MODEL_CARD.md`.

## Changing models

1. Edit `ml/models/model_manifest.json`: model ids, **pinned revisions**, `runtime`, parameters.
2. Bump `pipeline_version`. If the embedder, the sparse encoder or the chunking changed, also
   change `index_compat_id`: the backend then refuses the old index until a reindex.
3. Rebuild and restart `ml-service`, then `python -m indexer --data-dir /data/processed` in the
   backend container. The old collection stays for rollback: restore the previous manifest and
   move the alias back.
4. Run `uv run pytest` in `ml/`, and `uv run pytest -m ml` in `backend/` against the running
   service.

## Runtimes

`embedder.runtime`: `sentence-transformers` or `hash` (offline stand-in).
`reranker.runtime`: `cross-encoder` or `lexical` (offline stand-in).
A fine-tuned model is used by pointing `hf_repo` (a Hub repo or a local path) at it.
