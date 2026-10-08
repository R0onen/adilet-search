"""Indexer CLI.

    python -m indexer --data-dir data/sample [--manifest ml/models/model_manifest.json]
                      [--embeddings data/index/embeddings_0.1.0.parquet] [--batch-size 64]
                      [--no-switch] [--no-prune]

Without `--manifest`, the manifest comes from MANIFEST_SOURCE (default: ml-service /version).
Connection settings (DATABASE_URL, QDRANT_URL, ML_SERVICE_URL, …) come from the environment.
Exit code 0 on success, 1 on a validation/indexing error, 2 when another job is running.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.schemas.ml import Manifest
from app.state import Resources
from indexer.corpus import CorpusError
from indexer.pipeline import Indexer, IndexingError, IndexOptions, JobConflict

log = structlog.get_logger("indexer")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m indexer", description=__doc__.split("\n")[1])
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, help="model_manifest.json (default: MANIFEST_SOURCE)"
    )
    parser.add_argument("--embeddings", type=Path, help="precomputed embeddings Parquet")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--no-switch", action="store_true", help="build, but keep the alias")
    parser.add_argument("--no-prune", action="store_true", help="keep DB rows not in the data")
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    resources = Resources.create(settings)
    try:
        if args.manifest:
            manifest = Manifest.model_validate(json.loads(args.manifest.read_text("utf-8")))
        else:
            loaded = await resources.manifest.get()
            if loaded is None:
                log.error("manifest_unavailable", source=settings.manifest_source)
                return 1
            manifest = loaded
        indexer = Indexer(resources.sessionmaker, resources.qdrant, resources.ml, manifest)
        result = await indexer.run(
            IndexOptions(
                data_dir=args.data_dir,
                embeddings=args.embeddings,
                batch_size=args.batch_size,
                switch_alias=not args.no_switch,
                prune=not args.no_prune,
            )
        )
    except JobConflict as exc:
        log.error("job_conflict", error=str(exc))
        return 2
    except (CorpusError, IndexingError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        await resources.aclose()

    log.info(
        "index_done",
        job_id=str(result.job_id),
        collection=result.collection,
        previous_collection=result.previous_collection,
        alias_switched=result.switched,
        points=result.points,
        documents=result.documents,
        articles=result.articles,
        pg_documents=vars(result.pg_documents),
        pg_articles=vars(result.pg_articles),
        duration_s=round(result.duration_s, 2),
        timings_s={k: round(v, 2) for k, v in result.timings_s.items()},
        pipeline_version=manifest.pipeline_version,
        index_compat_id=manifest.index_compat_id,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
