from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import yaml

from test_workflow.targets import TargetManager, TargetManifest


def _create_local_target(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "source"
    repository.mkdir()
    (repository / "index.html").write_text("<h1>target-ready</h1>", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Workflow"], cwd=repository, check=True
    )
    subprocess.run(["git", "add", "index.html"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "target fixture"], cwd=repository, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    return repository, revision


def _write_manifest(tmp_path: Path, repository: Path, revision: str) -> Path:
    manifest = {
        "id": "local-target",
        "repository": str(repository),
        "revision": revision,
        "start_command": [
            sys.executable,
            "-m",
            "http.server",
            "${PORT}",
            "--bind",
            "127.0.0.1",
        ],
        "required_files": ["index.html"],
    }
    manifest_path = tmp_path / "target.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return manifest_path


def test_target_manifest_rejects_path_escape() -> None:
    with pytest.raises(ValueError, match="subdirectory"):
        TargetManifest.model_validate(
            {
                "id": "invalid",
                "repository": ".",
                "revision": "abcdef0",
                "subdirectory": "../outside",
                "start_command": ["python"],
            }
        )


def test_target_manager_materializes_exact_revision_and_serves(tmp_path: Path) -> None:
    repository, revision = _create_local_target(tmp_path)
    manifest_path = _write_manifest(tmp_path, repository, revision)
    manager = TargetManager()

    target = manager.materialize(manifest_path, tmp_path / "checkout", install=False)

    assert target.revision == revision
    assert (target.app_dir / "index.html").is_file()
    with manager.process(target, timeout_seconds=5) as running:
        response = httpx.get(running.base_url, timeout=2)
        assert response.status_code == 200
        assert "target-ready" in response.text


def test_target_manager_rejects_revision_drift(tmp_path: Path) -> None:
    repository, revision = _create_local_target(tmp_path)
    manifest_path = _write_manifest(tmp_path, repository, revision)
    manager = TargetManager()
    target = manager.materialize(manifest_path, tmp_path / "checkout", install=False)

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["revision"] = "0" * 40
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="revision mismatch"):
        manager.validate_checkout(manifest_path, target.checkout_dir)
