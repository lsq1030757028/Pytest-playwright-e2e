from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .control_plane import build_runtime
from .integrity import collect_file_hashes, sha256_file
from .mocking import validate_mock_configuration
from .serialization import dump_model, load_model
from .specs import (
    DataSeedSpec,
    EnvironmentSpec,
    ReplayArtifact,
    ReplayManifest,
    TestSpec,
    ValidationIssue,
    ValidationReport,
)


def _issue(code: str, message: str, path: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, path=path)


def create_replay_manifest(
    bundle_root: str | Path,
    *,
    command: list[str],
    browser: str = "chromium",
    run_id: str | None = None,
) -> ReplayManifest:
    root = Path(bundle_root).resolve()
    prevalidation = validate_replay_bundle(root, verify_manifest=False)
    if not prevalidation.valid:
        raise ValueError(prevalidation.model_dump_json(indent=2))
    environment = load_model(
        root / "environment" / "environment-spec.yaml", EnvironmentSpec
    )
    load_model(root / "spec" / "test-spec.yaml", TestSpec)
    load_model(root / environment.data_seed_path, DataSeedSpec)

    artifacts = [
        ReplayArtifact(path=path, sha256=digest)
        for path, digest in collect_file_hashes(root).items()
    ]
    manifest = ReplayManifest(
        run_id=run_id or f"run-{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(UTC),
        command=command,
        browser=browser,
        python_version=sys.version.split()[0],
        random_seed=environment.random_seed,
        artifacts=artifacts,
    )
    dump_model(root / "replay-manifest.yaml", manifest)
    return manifest


def validate_replay_bundle(
    bundle_root: str | Path,
    *,
    verify_manifest: bool = True,
) -> ValidationReport:
    root = Path(bundle_root).resolve()
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    required = [
        root / "spec" / "test-spec.yaml",
        root / "environment" / "environment-spec.yaml",
        root / "environment" / "mock-plan.yaml",
        root / "environment" / "data-seed.yaml",
    ]
    for path in required:
        if not path.is_file():
            errors.append(
                _issue("bundle.required_file_missing", "required file missing", str(path))
            )

    if errors:
        return ValidationReport(valid=False, errors=errors)

    try:
        load_model(root / "spec" / "test-spec.yaml", TestSpec)
        environment = load_model(
            root / "environment" / "environment-spec.yaml", EnvironmentSpec
        )
        load_model(root / environment.data_seed_path, DataSeedSpec)
    except (OSError, ValueError) as exc:
        errors.append(_issue("bundle.document_invalid", str(exc)))

    mock_report = validate_mock_configuration(root)
    errors.extend(mock_report.errors)
    warnings.extend(mock_report.warnings)

    manifest_path = root / "replay-manifest.yaml"
    if verify_manifest:
        if not manifest_path.is_file():
            errors.append(
                _issue(
                    "bundle.manifest_missing",
                    "replay-manifest.yaml is required for independent replay",
                    str(manifest_path),
                )
            )
        else:
            try:
                manifest = load_model(manifest_path, ReplayManifest)
            except ValueError as exc:
                errors.append(_issue("bundle.manifest_invalid", str(exc)))
            else:
                expected = {artifact.path: artifact.sha256 for artifact in manifest.artifacts}
                current = collect_file_hashes(root)
                missing = sorted(set(expected) - set(current))
                unexpected = sorted(set(current) - set(expected))
                for path in missing:
                    errors.append(
                        _issue("bundle.artifact_missing", "tracked artifact missing", path)
                    )
                for path in unexpected:
                    errors.append(
                        _issue("bundle.artifact_untracked", "untracked artifact found", path)
                    )
                for path in sorted(set(expected) & set(current)):
                    if expected[path] != current[path]:
                        errors.append(
                            _issue(
                                "bundle.artifact_hash_mismatch",
                                f"expected {expected[path]}, got {current[path]}",
                                path,
                            )
                        )

    return ValidationReport(valid=not errors, errors=errors, warnings=warnings)


def replay_bundle(bundle_root: str | Path) -> int:
    root = Path(bundle_root).resolve()
    report = validate_replay_bundle(root)
    if not report.valid:
        raise ValueError(report.model_dump_json(indent=2))

    manifest = load_model(root / "replay-manifest.yaml", ReplayManifest)
    runtime = build_runtime(root)
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    environment["TEST_WORKFLOW_BUNDLE_ROOT"] = str(root)
    environment["TEST_WORKFLOW_STORAGE_STATE"] = str(runtime.storage_state_path)
    environment["TEST_WORKFLOW_INIT_SCRIPT"] = str(runtime.init_script_path)
    environment["TEST_WORKFLOW_RANDOM_SEED"] = str(manifest.random_seed)
    package_src = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(package_src), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    started_at = datetime.now(UTC)
    completed = subprocess.run(
        manifest.command,
        cwd=root,
        env=environment,
        check=False,
        text=True,
        capture_output=True,
    )
    finished_at = datetime.now(UTC)
    (evidence_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (evidence_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    result_path = evidence_dir / "replay-result.json"
    result_path.write_text(
        json.dumps(
            {
                "run_id": manifest.run_id,
                "command": manifest.command,
                "return_code": completed.returncode,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "manifest_sha256": sha256_file(root / "replay-manifest.yaml"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return completed.returncode
