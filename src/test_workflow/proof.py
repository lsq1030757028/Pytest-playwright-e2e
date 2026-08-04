from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .integrity import sha256_file
from .serialization import load_model
from .targets import MaterializedTarget, TargetManager


ProofPhase = Literal["baseline", "mutation", "restored"]


class TextMutationSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    description: str = Field(min_length=1)
    target_path: str
    find: str = Field(min_length=1)
    replace: str
    critical: bool = True

    @model_validator(mode="after")
    def validate_mutation(self) -> TextMutationSpec:
        path = Path(self.target_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("mutation target_path must remain inside the target checkout")
        if self.find == self.replace:
            raise ValueError("mutation replacement must change the target content")
        return self


class MutationProofPlan(BaseModel):
    schema_version: str = "1.0"
    id: str
    project_root: str = "."
    target_manifest: str
    test_command: list[str] = Field(min_length=1)
    target_url_env: str = "TODO_TARGET_URL"
    stability_runs: int = Field(default=3, ge=1, le=10)
    mutations: list[TextMutationSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_paths_and_ids(self) -> MutationProofPlan:
        for field_name in ("project_root", "target_manifest"):
            value = Path(getattr(self, field_name))
            if value.is_absolute():
                raise ValueError(f"{field_name} must be relative")
        ids = [mutation.id for mutation in self.mutations]
        if len(ids) != len(set(ids)):
            raise ValueError("mutation ids must be unique")
        return self


class ProofExecution(BaseModel):
    phase: ProofPhase
    attempt: int = Field(ge=1)
    mutation_id: str | None = None
    return_code: int
    duration_seconds: float = Field(ge=0)
    stdout_path: str
    stderr_path: str
    junit_path: str

    @property
    def passed(self) -> bool:
        return self.return_code == 0


class MutationResult(BaseModel):
    mutation_id: str
    description: str
    critical: bool
    killed: bool
    original_sha256: str
    mutated_sha256: str
    restored_sha256: str
    execution: ProofExecution


class MutationProofReport(BaseModel):
    schema_version: str = "1.0"
    plan_id: str
    target_revision: str
    status: Literal["passed", "failed"]
    baseline: list[ProofExecution]
    mutations: list[MutationResult]
    restored: list[ProofExecution]
    mutation_score: float = Field(ge=0, le=1)
    critical_false_green: int = Field(ge=0)
    evidence_dir: str


@dataclass(frozen=True)
class AppliedMutation:
    path: Path
    original_sha256: str
    mutated_sha256: str


class TextMutation(AbstractContextManager[AppliedMutation]):
    def __init__(self, app_dir: Path, spec: TextMutationSpec) -> None:
        self.app_dir = app_dir.resolve()
        self.spec = spec
        self.path = (self.app_dir / spec.target_path).resolve()
        self._original: str | None = None
        self._original_sha256: str | None = None

    def __enter__(self) -> AppliedMutation:
        if not self.path.is_relative_to(self.app_dir):
            raise ValueError("mutation path escaped target application directory")
        if not self.path.is_file():
            raise ValueError(f"mutation target file does not exist: {self.spec.target_path}")

        original = self.path.read_text(encoding="utf-8")
        match_count = original.count(self.spec.find)
        if match_count != 1:
            raise ValueError(
                f"mutation {self.spec.id!r} expected one exact match in "
                f"{self.spec.target_path}, found {match_count}"
            )

        self._original = original
        self._original_sha256 = sha256_file(self.path)
        mutated = original.replace(self.spec.find, self.spec.replace, 1)
        self.path.write_text(mutated, encoding="utf-8")
        return AppliedMutation(
            path=self.path,
            original_sha256=self._original_sha256,
            mutated_sha256=sha256_file(self.path),
        )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._original is not None:
            self.path.write_text(self._original, encoding="utf-8")
        return None

    def restored_sha256(self) -> str:
        if self._original_sha256 is None:
            raise RuntimeError("mutation has not been applied")
        restored = sha256_file(self.path)
        if restored != self._original_sha256:
            raise RuntimeError(f"mutation {self.spec.id!r} did not restore the original file")
        return restored


@dataclass(frozen=True)
class LoadedProofPlan:
    plan: MutationProofPlan
    plan_path: Path
    project_root: Path
    target_manifest: Path


class MutationProofRunner:
    def __init__(self, target_manager: TargetManager | None = None) -> None:
        self.target_manager = target_manager or TargetManager()

    def load_plan(self, plan_path: str | Path) -> LoadedProofPlan:
        resolved_plan_path = Path(plan_path).resolve()
        plan = load_model(resolved_plan_path, MutationProofPlan)
        project_root = (resolved_plan_path.parent / plan.project_root).resolve()
        target_manifest = (project_root / plan.target_manifest).resolve()
        if not target_manifest.is_relative_to(project_root):
            raise ValueError("target_manifest escaped project_root")
        if not target_manifest.is_file():
            raise ValueError(f"target manifest does not exist: {target_manifest}")
        return LoadedProofPlan(plan, resolved_plan_path, project_root, target_manifest)

    def run(
        self,
        plan_path: str | Path,
        *,
        workspace: str | Path,
        evidence_dir: str | Path,
    ) -> MutationProofReport:
        loaded = self.load_plan(plan_path)
        workspace_path = Path(workspace).resolve()
        evidence_path = Path(evidence_dir).resolve()
        workspace_path.mkdir(parents=True, exist_ok=True)
        evidence_path.mkdir(parents=True, exist_ok=True)

        target = self.target_manager.materialize(
            loaded.target_manifest,
            workspace_path / "target",
        )
        baseline = [
            self._execute_target(
                loaded,
                target,
                evidence_path,
                phase="baseline",
                attempt=attempt,
            )
            for attempt in range(1, loaded.plan.stability_runs + 1)
        ]

        mutation_results: list[MutationResult] = []
        for mutation in loaded.plan.mutations:
            patch = TextMutation(target.app_dir, mutation)
            with patch as applied:
                execution = self._execute_target(
                    loaded,
                    target,
                    evidence_path,
                    phase="mutation",
                    attempt=1,
                    mutation_id=mutation.id,
                )
            restored_hash = patch.restored_sha256()
            mutation_results.append(
                MutationResult(
                    mutation_id=mutation.id,
                    description=mutation.description,
                    critical=mutation.critical,
                    killed=not execution.passed,
                    original_sha256=applied.original_sha256,
                    mutated_sha256=applied.mutated_sha256,
                    restored_sha256=restored_hash,
                    execution=execution,
                )
            )

        restored = [
            self._execute_target(
                loaded,
                target,
                evidence_path,
                phase="restored",
                attempt=attempt,
            )
            for attempt in range(1, loaded.plan.stability_runs + 1)
        ]

        killed = sum(result.killed for result in mutation_results)
        mutation_score = killed / len(mutation_results)
        critical_false_green = sum(
            result.critical and not result.killed for result in mutation_results
        )
        passed = (
            all(item.passed for item in baseline)
            and all(item.killed for item in mutation_results)
            and all(item.passed for item in restored)
            and critical_false_green == 0
        )
        report = MutationProofReport(
            plan_id=loaded.plan.id,
            target_revision=target.revision,
            status="passed" if passed else "failed",
            baseline=baseline,
            mutations=mutation_results,
            restored=restored,
            mutation_score=mutation_score,
            critical_false_green=critical_false_green,
            evidence_dir=str(evidence_path),
        )
        (evidence_path / "proof-report.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        (evidence_path / "proof-report.md").write_text(
            render_proof_markdown(report), encoding="utf-8"
        )
        return report

    def _execute_target(
        self,
        loaded: LoadedProofPlan,
        target: MaterializedTarget,
        evidence_dir: Path,
        *,
        phase: ProofPhase,
        attempt: int,
        mutation_id: str | None = None,
    ) -> ProofExecution:
        run_name = f"{phase}-{mutation_id or attempt}"
        run_dir = evidence_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        with self.target_manager.process(
            target,
            timeout_seconds=30,
            log_dir=run_dir / "target-logs",
        ) as running:
            command = normalize_test_command(loaded.plan.test_command)
            command.extend(
                [
                    "--output",
                    str(run_dir / "playwright"),
                    f"--junitxml={run_dir / 'junit.xml'}",
                ]
            )
            environment = os.environ.copy()
            environment[loaded.plan.target_url_env] = running.base_url
            started = time.monotonic()
            completed = subprocess.run(
                command,
                cwd=loaded.project_root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            duration = time.monotonic() - started

        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        return ProofExecution(
            phase=phase,
            attempt=attempt,
            mutation_id=mutation_id,
            return_code=completed.returncode,
            duration_seconds=duration,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            junit_path=str(run_dir / "junit.xml"),
        )


def normalize_test_command(command: list[str]) -> list[str]:
    normalized = list(command)
    if normalized[0] in {"python", "python3"}:
        normalized[0] = sys.executable
    return normalized


def render_proof_markdown(report: MutationProofReport) -> str:
    lines = [
        f"# Mutation Proof: {report.plan_id}",
        "",
        f"- Status: **{report.status.upper()}**",
        f"- Target revision: `{report.target_revision}`",
        f"- Mutation score: `{report.mutation_score:.0%}`",
        f"- Critical false green: `{report.critical_false_green}`",
        "",
        "## State machine",
        "",
        "```text",
        f"Baseline: {'PASS' if all(item.passed for item in report.baseline) else 'FAIL'}",
        f"Mutation: {sum(item.killed for item in report.mutations)}/{len(report.mutations)} killed",
        f"Restored: {'PASS' if all(item.passed for item in report.restored) else 'FAIL'}",
        "```",
        "",
        "## Mutations",
        "",
        "| Mutation | Critical | Result |",
        "|---|---:|---|",
    ]
    for mutation in report.mutations:
        lines.append(
            f"| `{mutation.mutation_id}` | {'yes' if mutation.critical else 'no'} | "
            f"{'KILLED' if mutation.killed else 'SURVIVED'} |"
        )
    lines.append("")
    return "\n".join(lines)
