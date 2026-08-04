from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_file_hashes(
    root: str | Path,
    *,
    excluded_names: set[str] | None = None,
    excluded_prefixes: tuple[str, ...] = (
        ".runtime/",
        "evidence/",
        ".pytest_cache/",
        ".ruff_cache/",
    ),
) -> dict[str, str]:
    root_path = Path(root)
    excluded_names = excluded_names or {"replay-manifest.yaml", "replay-manifest.json"}
    result: dict[str, str] = {}
    for file_path in sorted(path for path in root_path.rglob("*") if path.is_file()):
        relative = file_path.relative_to(root_path).as_posix()
        if file_path.name in excluded_names or file_path.suffix in {".pyc", ".pyo"}:
            continue
        if "__pycache__" in file_path.parts:
            continue
        if any(relative.startswith(prefix) for prefix in excluded_prefixes):
            continue
        result[relative] = sha256_file(file_path)
    return result
