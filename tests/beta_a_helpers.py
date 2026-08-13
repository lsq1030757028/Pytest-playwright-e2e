from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from test_workflow.beta_runtime.models import SubmissionBundle, load_submission_bundle


def _run(*args: str, cwd: Path) -> str:
    process = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout.strip()


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def make_governed_fixture(
    root: Path,
    *,
    image: str = "beta-a-runtime-ci:1",
    repository: str = "https://example.invalid/beta-a-fixture.git",
    test_source: str | None = None,
    idempotency_key: str = "beta-a-fixture-key",
) -> tuple[SubmissionBundle, Path, Path, Path]:
    project = root / "project"
    manifests = root / "manifests"
    project.mkdir(parents=True)
    manifests.mkdir(parents=True)

    source = test_source or (
        "def test_governed_unit():\n"
        "    assert 2 + 2 == 4\n"
    )
    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_governed.py").write_text(source, encoding="utf-8")

    _run("git", "init", "-q", cwd=project)
    _run("git", "config", "user.email", "beta-a@example.invalid", cwd=project)
    _run("git", "config", "user.name", "BETA-A Fixture", cwd=project)
    _run("git", "remote", "add", "origin", repository, cwd=project)
    _run("git", "add", ".", cwd=project)
    _run("git", "commit", "-q", "-m", "fixture", cwd=project)
    commit_sha = _run("git", "rev-parse", "HEAD", cwd=project)

    project_manifest = {
        "profile_id": "beta-a-project-v1",
        "repository": repository,
        "checkout_path": str(project),
        "commit_sha": commit_sha,
    }
    objective_manifest = {
        "objective_id": "beta-a-objective-v1",
        "summary": "Execute the existing governed pack only.",
    }
    environment_manifest = {
        "profile_id": "beta-a-env-v1",
        "backend": "DOCKER",
        "image": image,
        "network": "DENY",
    }
    budget_manifest = {
        "wall_clock_job_minutes": 5,
        "execution_attempt_minutes": 2,
        "execution_attempts": 1,
        "workers_per_job": 1,
        "browser_contexts_per_attempt": 1,
        "artifact_mebibytes": 50,
        "automatic_retries": 0,
    }
    evidence_manifest = {
        "profile_id": "beta-a-evidence-v1",
        "capture": ["junit", "runtime_report", "stdout", "stderr"],
    }
    oracle_manifest = {
        "oracle_id": "beta-a-oracle-v1",
        "status": "ACTIVE",
        "authority": "AUTHORITATIVE",
        "project_repository": repository,
        "commit_sha": commit_sha,
        "assertion": "All required governed nodes pass.",
    }
    node_id = "tests/test_governed.py::test_governed_unit"
    pack_manifest = {
        "pack_id": "beta-a-pack",
        "pack_version": "1.0.0",
        "project_profile_ref": "project.yaml",
        "commit_sha": commit_sha,
        "framework": "pytest",
        "selected_node_ids": [node_id],
        "required_node_ids": [node_id],
        "node_oracle_bindings": {node_id: "oracle.yaml"},
        "environment_profile_ref": "environment.yaml",
        "evidence_profile_ref": "evidence.yaml",
    }

    write_yaml(manifests / "project.yaml", project_manifest)
    write_yaml(manifests / "objective.yaml", objective_manifest)
    write_yaml(manifests / "environment.yaml", environment_manifest)
    write_yaml(manifests / "budget.yaml", budget_manifest)
    write_yaml(manifests / "evidence.yaml", evidence_manifest)
    write_yaml(manifests / "oracle.yaml", oracle_manifest)
    write_yaml(manifests / "pack.yaml", pack_manifest)

    submission = {
        "idempotency_key": idempotency_key,
        "project_repository": repository,
        "commit_sha": commit_sha,
        "project_profile_ref": "project.yaml",
        "objective_manifest_ref": "objective.yaml",
        "governed_pack_manifest_ref": "pack.yaml",
        "permitted_test_paths": ["tests"],
        "permitted_capabilities": ["pytest"],
        "oracle_refs": ["oracle.yaml"],
        "environment_profile_ref": "environment.yaml",
        "budget_profile_ref": "budget.yaml",
        "evidence_profile_ref": "evidence.yaml",
    }
    submission_path = manifests / "submission.yaml"
    write_yaml(submission_path, submission)
    return load_submission_bundle(submission_path), project, manifests, submission_path
