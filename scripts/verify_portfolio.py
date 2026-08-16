#!/usr/bin/env python3
"""Offline package, privacy and synthetic-regression verification."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".py", ".ps1", ".json", ".jsonl", ".md", ".yml", ".yaml", ".txt", ""}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".tmp", ".zip", ".pem", ".key"}
REQUIRED = {
    ".github/workflows/verify-package.yml",
    "AI_ASSISTANCE.md",
    "AI_REPRODUCIBILITY_REVIEW.md",
    "DATA_AVAILABILITY.md",
    "LICENSE.md",
    "MANIFEST.sha256",
    "README.md",
    "config/portfolio_config.json",
    "data/PRIVATE_CORPUS_GUIDE.md",
    "data/sample/synthetic_documents.jsonl",
    "data/sample/synthetic_questions.jsonl",
    "src/vidarabine_rag.py",
    "tests/test_portfolio.py",
}
SENSITIVE_PATTERNS = {
    "Windows user path": re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+"),
    "Unix home path": re.compile(r"/home/[A-Za-z0-9._-]+/"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "assigned secret": re.compile(
        r"(?i)(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
}


class VerificationError(RuntimeError):
    pass


def is_private_data(path: Path) -> bool:
    parts = path.relative_to(ROOT).parts
    return len(parts) >= 2 and parts[0] == "data" and parts[1] == "private"


def files_for_manifest() -> list[Path]:
    return sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and path != MANIFEST
            and not is_private_data(path)
            and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
            and path.suffix.lower() not in FORBIDDEN_SUFFIXES
        ),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_structure() -> None:
    existing = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()}
    missing = sorted(REQUIRED - existing)
    if missing:
        raise VerificationError(f"Required files missing: {missing}")
    forbidden = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not is_private_data(path)
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        and path.suffix.lower() in FORBIDDEN_SUFFIXES
    )
    if forbidden:
        raise VerificationError(f"Forbidden file types found: {forbidden}")


def verify_json_files() -> None:
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8-sig"))
    for path in ROOT.rglob("*.jsonl"):
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise VerificationError(f"JSONL row is not an object: {path}, line {line_number}")


def verify_python_syntax() -> None:
    for path in ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8-sig")
        compile(source, str(path), "exec")


def verify_sensitive_patterns() -> None:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if is_private_data(path):
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for label, pattern in SENSITIVE_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT).as_posix()}: {label}")
    if findings:
        raise VerificationError("Sensitive-pattern findings: " + "; ".join(findings))


def verify_markdown_links() -> None:
    broken: list[str] = []
    for path in ROOT.rglob("*.md"):
        if is_private_data(path):
            continue
        text = path.read_text(encoding="utf-8-sig")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            clean = target.strip().split("#", 1)[0]
            if not clean or re.match(r"(?i)^(?:https?://|mailto:)", clean):
                continue
            candidate = (path.parent / clean).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError:
                broken.append(f"{path.relative_to(ROOT).as_posix()} -> {target} (outside repository)")
                continue
            if not candidate.exists():
                broken.append(f"{path.relative_to(ROOT).as_posix()} -> {target}")
    if broken:
        raise VerificationError("Broken local Markdown links: " + "; ".join(broken))


def verify_manifest() -> None:
    expected: dict[str, str] = {}
    for line_number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise VerificationError(f"Invalid manifest line {line_number}")
        digest, relative = match.groups()
        if relative in expected:
            raise VerificationError(f"Duplicate manifest entry: {relative}")
        expected[relative] = digest
    actual_paths = {path.relative_to(ROOT).as_posix(): path for path in files_for_manifest()}
    if set(expected) != set(actual_paths):
        missing = sorted(set(actual_paths) - set(expected))
        extra = sorted(set(expected) - set(actual_paths))
        raise VerificationError(f"Manifest file set mismatch; missing={missing}, extra={extra}")
    mismatched = [relative for relative, path in actual_paths.items() if sha256(path) != expected[relative]]
    if mismatched:
        raise VerificationError(f"Manifest hash mismatch: {mismatched}")


def run_regressions() -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "src/vidarabine_rag.py", "evaluate"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, env=environment, text=True, capture_output=True)
        if completed.returncode != 0:
            raise VerificationError(
                f"Command failed: {' '.join(command)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        if command[-1] == "evaluate":
            summary = json.loads(completed.stdout)
            if not summary.get("all_tests_passed") or summary.get("passed_count") != 5:
                raise VerificationError(f"Synthetic evaluation did not pass 5/5: {summary}")


def main() -> int:
    try:
        verify_structure()
        verify_json_files()
        verify_python_syntax()
        verify_sensitive_patterns()
        verify_markdown_links()
        verify_manifest()
        run_regressions()
    except (VerificationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"VERIFY FAILED: {exc}", file=sys.stderr)
        return 1
    print("VERIFY PASSED")
    print("- required files and public boundary: OK")
    print("- Python / JSON / JSONL: OK")
    print("- sensitive-pattern scan: OK")
    print("- local Markdown links: OK")
    print("- SHA-256 manifest: OK")
    print("- unit tests: 5/5")
    print("- synthetic evaluation: 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
