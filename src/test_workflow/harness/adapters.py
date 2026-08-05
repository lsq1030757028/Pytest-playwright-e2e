from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..proof import MutationProofRunner
from ..serialization import load_model
from ..specs import TestSpec
from ..targets import TargetManager
from .artifacts import StoreExecutionContext, canonical_json_bytes
from .contracts import (
    ArtifactTypeRef,
    CapabilityAccess,
    CapabilityDescriptor,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    ContextLevel,
    ContextRequest,
    ExecutionMetrics,
    PermissionScope,
)


class AdapterInputError(ValueError):
    pass


class SpecValidateCapability:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="spec.validate",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="SpecSource", schema_version=1),),
            output_types=(ArtifactTypeRef(name="SpecValidation", schema_version=1),),
            default_context=ContextRequest(level=ContextLevel.METADATA),
            required_permissions=PermissionScope(
                read=frozenset({"artifacts/spec/*", "repository/specs/*"}),
                write=frozenset({"artifacts/validation/*"}),
            ),
            timeout_seconds=5,
        )

    def execute(
        self,
        request: CapabilityRequest,
        context: StoreExecutionContext,
    ) -> CapabilityResult:
        source = _single_input(context, request, "SpecSource")
        path = _safe_path(self.repo_root, _required_string(source, "path"))
        started = time.perf_counter()
        try:
            spec = load_model(path, TestSpec)
            content = {
                "valid": True,
                "path": str(path.relative_to(self.repo_root)),
                "spec_id": spec.id,
                "case_count": len(spec.cases),
                "oracle_count": sum(len(item.oracles) for item in spec.cases),
            }
            ref = context.write_artifact(
                artifact_id=_artifact_id("validation/spec", request.request_id),
                artifact_type="SpecValidation",
                schema_version=1,
                content=content,
                created_by=self.descriptor.ref,
                source_revisions={"spec": request.input_artifacts[0].artifact_id},
            )
            return _success(request, ref, content, started)
        except Exception as exc:
            return _failure(request, exc, started)


class TargetManifestValidateCapability:
    def __init__(self, repo_root: Path, manager: TargetManager | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.manager = manager or TargetManager()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="target.validate",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="TargetSource", schema_version=1),),
            output_types=(ArtifactTypeRef(name="TargetValidation", schema_version=1),),
            default_context=ContextRequest(level=ContextLevel.METADATA),
            required_permissions=PermissionScope(
                read=frozenset({"artifacts/target/*", "repository/targets/*"}),
                write=frozenset({"artifacts/validation/*"}),
            ),
            timeout_seconds=5,
        )

    def execute(
        self,
        request: CapabilityRequest,
        context: StoreExecutionContext,
    ) -> CapabilityResult:
        source = _single_input(context, request, "TargetSource")
        path = _safe_path(self.repo_root, _required_string(source, "path"))
        started = time.perf_counter()
        try:
            manifest = self.manager.load_manifest(path)
            content = {
                "valid": True,
                "path": str(path.relative_to(self.repo_root)),
                "target_id": manifest.id,
                "repository": manifest.repository,
                "revision": manifest.revision,
                "required_files": list(manifest.required_files),
            }
            ref = context.write_artifact(
                artifact_id=_artifact_id("validation/target", request.request_id),
                artifact_type="TargetValidation",
                schema_version=1,
                content=content,
                created_by=self.descriptor.ref,
                source_revisions={"target": request.input_artifacts[0].artifact_id},
            )
            return _success(request, ref, content, started)
        except Exception as exc:
            return _failure(request, exc, started)


class PytestRunCapability:
    ALLOWED_ARGS = frozenset({"-q", "-x", "--disable-warnings"})

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="test.run",
            version="1.0.0",
            output_types=(ArtifactTypeRef(name="TestRunResult", schema_version=1),),
            default_context=ContextRequest(level=ContextLevel.METADATA),
            required_permissions=PermissionScope(
                read=frozenset({"repository/tests/*"}),
                write=frozenset({"artifacts/test-runs/*"}),
                execute=frozenset({"pytest"}),
                allow_subprocess=True,
            ),
            access=CapabilityAccess(allow_subprocess=True),
            timeout_seconds=120,
        )

    def execute(
        self,
        request: CapabilityRequest,
        context: StoreExecutionContext,
    ) -> CapabilityResult:
        started = time.perf_counter()
        try:
            test_paths = request.parameters.get("tests")
            if not isinstance(test_paths, list) or not test_paths:
                raise AdapterInputError("parameters.tests must be a non-empty list")
            resolved_tests = [self._test_path(item) for item in test_paths]
            extra_args = request.parameters.get("pytest_args", [])
            if not isinstance(extra_args, list) or any(
                item not in self.ALLOWED_ARGS for item in extra_args
            ):
                raise AdapterInputError("pytest_args contains an unsupported option")
            command = [
                sys.executable,
                "-m",
                "pytest",
                *(str(path.relative_to(self.repo_root)) for path in resolved_tests),
                *extra_args,
            ]
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                text=True,
                capture_output=True,
                timeout=request.budget.wall_time_seconds,
                check=False,
            )
            content = {
                "command": command,
                "return_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "tests": [str(path.relative_to(self.repo_root)) for path in resolved_tests],
            }
            ref = context.write_artifact(
                artifact_id=_artifact_id("test-runs", request.request_id),
                artifact_type="TestRunResult",
                schema_version=1,
                content=content,
                created_by=self.descriptor.ref,
            )
            metrics = _metrics(started, content, subprocesses=1)
            if completed.returncode == 0:
                return CapabilityResult(
                    request_id=request.request_id,
                    status=CapabilityResultStatus.SUCCESS,
                    artifacts=(ref,),
                    metrics=metrics,
                )
            return CapabilityResult(
                request_id=request.request_id,
                status=CapabilityResultStatus.FAILED,
                artifacts=(ref,),
                metrics=metrics,
                error=f"pytest exited with code {completed.returncode}",
            )
        except Exception as exc:
            return _failure(request, exc, started, subprocesses=1)

    def _test_path(self, raw: Any) -> Path:
        if not isinstance(raw, str):
            raise AdapterInputError("test path must be a string")
        path = _safe_path(self.repo_root, raw)
        tests_root = (self.repo_root / "tests").resolve()
        if not path.is_relative_to(tests_root):
            raise AdapterInputError("test path must remain inside tests/")
        return path


class MutationProofCapability:
    def __init__(self, repo_root: Path, runner: MutationProofRunner | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.runner = runner or MutationProofRunner()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="proof.run",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="ProofSource", schema_version=1),),
            output_types=(ArtifactTypeRef(name="MutationProofReport", schema_version=1),),
            default_context=ContextRequest(level=ContextLevel.FOCUSED),
            required_permissions=PermissionScope(
                read=frozenset({"artifacts/proof/*", "repository/proofs/*"}),
                write=frozenset({"artifacts/proof-results/*", "workspaces/proof/*"}),
                execute=frozenset({"mutation-proof"}),
                network_domains=frozenset({"github.com"}),
                allow_subprocess=True,
            ),
            access=CapabilityAccess(allow_network=True, allow_subprocess=True),
            timeout_seconds=1800,
        )

    def execute(
        self,
        request: CapabilityRequest,
        context: StoreExecutionContext,
    ) -> CapabilityResult:
        source = _single_input(context, request, "ProofSource")
        started = time.perf_counter()
        try:
            plan = _safe_path(self.repo_root, _required_string(source, "path"))
            workspace = _safe_output_path(
                self.repo_root,
                request.parameters.get("workspace", ".harness-work/proof"),
            )
            evidence = _safe_output_path(
                self.repo_root,
                request.parameters.get("evidence", "test-results/harness-proof"),
            )
            report = self.runner.run(plan, workspace=workspace, evidence_dir=evidence)
            content = report.model_dump(mode="json")
            ref = context.write_artifact(
                artifact_id=_artifact_id("proof-results", request.request_id),
                artifact_type="MutationProofReport",
                schema_version=1,
                content=content,
                created_by=self.descriptor.ref,
                source_revisions={"proof": request.input_artifacts[0].artifact_id},
            )
            metrics = _metrics(started, content, api_calls=1, subprocesses=1)
            status = (
                CapabilityResultStatus.SUCCESS
                if report.status == "passed"
                else CapabilityResultStatus.FAILED
            )
            return CapabilityResult(
                request_id=request.request_id,
                status=status,
                artifacts=(ref,),
                metrics=metrics,
                error=None if status == CapabilityResultStatus.SUCCESS else "proof failed",
            )
        except Exception as exc:
            return _failure(request, exc, started, api_calls=1, subprocesses=1)


def register_existing_capabilities(registry: Any, repo_root: Path) -> None:
    registry.register(SpecValidateCapability(repo_root))
    registry.register(TargetManifestValidateCapability(repo_root))
    registry.register(PytestRunCapability(repo_root))
    registry.register(MutationProofCapability(repo_root))


def _single_input(
    context: StoreExecutionContext,
    request: CapabilityRequest,
    expected_type: str,
) -> dict[str, Any]:
    if len(request.input_artifacts) != 1:
        raise AdapterInputError(f"{expected_type} capability requires exactly one input")
    ref = request.input_artifacts[0]
    if ref.artifact_type != expected_type:
        raise AdapterInputError(f"expected {expected_type}, got {ref.artifact_type}")
    return context.read_artifact(ref)


def _required_string(content: dict[str, Any], key: str) -> str:
    value = content.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterInputError(f"{key} must be a non-empty string")
    return value


def _safe_path(root: Path, raw: str) -> Path:
    value = Path(raw)
    if value.is_absolute() or ".." in value.parts:
        raise AdapterInputError("path must be a safe relative path")
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root) or not resolved.exists():
        raise AdapterInputError(f"path does not exist inside repository: {raw}")
    return resolved


def _safe_output_path(root: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw:
        raise AdapterInputError("output path must be a non-empty string")
    value = Path(raw)
    if value.is_absolute() or ".." in value.parts:
        raise AdapterInputError("output path must be a safe relative path")
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root):
        raise AdapterInputError("output path escaped repository")
    return resolved


def _artifact_id(prefix: str, request_id: str) -> str:
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}/{digest}"


def _success(
    request: CapabilityRequest,
    ref: Any,
    content: dict[str, Any],
    started: float,
) -> CapabilityResult:
    return CapabilityResult(
        request_id=request.request_id,
        status=CapabilityResultStatus.SUCCESS,
        artifacts=(ref,),
        metrics=_metrics(started, content),
    )


def _failure(
    request: CapabilityRequest,
    exc: Exception,
    started: float,
    *,
    api_calls: int = 0,
    subprocesses: int = 0,
) -> CapabilityResult:
    return CapabilityResult(
        request_id=request.request_id,
        status=CapabilityResultStatus.FAILED,
        error=f"{type(exc).__name__}: {exc}",
        metrics=ExecutionMetrics(
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            api_calls=api_calls,
            subprocesses=subprocesses,
        ),
    )


def _metrics(
    started: float,
    content: dict[str, Any],
    *,
    api_calls: int = 0,
    subprocesses: int = 0,
) -> ExecutionMetrics:
    return ExecutionMetrics(
        duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
        api_calls=api_calls,
        subprocesses=subprocesses,
        artifact_bytes=len(canonical_json_bytes(content)),
    )
