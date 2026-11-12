"""Export reviewable working-tree source without Git metadata, secrets or runtime caches."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "Final Project"


def main() -> None:
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode("utf-8")
        .split("\0")
    )
    files = []
    for name in sorted(set(names) - {""}):
        path = ROOT / name
        if not path.is_file() or not path.resolve().is_relative_to(ROOT):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if any(
            part in {".git", ".venv", "node_modules", "test-results"}
            for part in path.parts
        ):
            continue
        files.append(path)
    manifest = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }
    OUT.mkdir(exist_ok=True)
    source = OUT / "Adilet_Search_Source.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, "adilet-search/" + path.relative_to(ROOT).as_posix())
        archive.writestr("source_manifest.json", json.dumps(manifest, indent=2) + "\n")
    (OUT / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        assert not any(
            n.endswith("/.env.final") or "/node_modules/" in n
            for n in archive.namelist()
        )
    print(f"Exported {len(files)} source files; {source.stat().st_size:,} bytes")
    print(
        "Review draft: outstanding requirements remain in docs/report/final_readiness.md"
    )


if __name__ == "__main__":
    main()
