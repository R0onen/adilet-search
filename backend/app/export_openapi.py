"""Write `contracts/openapi.json` from the app code (`uv run python -m app.export_openapi`).

Keys are sorted and the output ends with a newline, so regeneration is byte-stable and CI can
fail on drift with `git diff --exit-code contracts/openapi.json`.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from app import __version__
from app.core.config import Settings
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "contracts" / "openapi.json"


def build_schema() -> dict[str, Any]:
    # Fixed settings: the schema must not depend on the local environment.
    settings = Settings(_env_file=None, environment="dev", app_version=__version__)
    app = create_app(settings)
    return app.openapi()


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the file is missing or stale"
    )
    args = parser.parse_args()

    content = render(build_schema())
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != content:
            raise SystemExit(f"{args.output} is stale: run `uv run python -m app.export_openapi`")
        print(f"{args.output} is up to date")
        return
    args.output.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
