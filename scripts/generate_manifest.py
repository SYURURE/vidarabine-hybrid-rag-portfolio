#!/usr/bin/env python3
"""Generate the SHA-256 manifest for the public portfolio."""
from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache"}


def is_private_data(path: Path) -> bool:
    parts = path.relative_to(ROOT).parts
    return len(parts) >= 2 and parts[0] == "data" and parts[1] == "private"


def included_files() -> list[Path]:
    return sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and path != MANIFEST
            and not is_private_data(path)
            and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
            and path.suffix.lower() not in {".pyc", ".tmp", ".zip"}
        ),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in included_files()]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {MANIFEST.name}: {len(lines)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
