from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from ..specs import TestSpec
from .contracts import FrozenModel
from .intelligence import ModelProvider, UnderstandingArtifact


class CompiledSpecArtifact(FrozenModel):
    requirement_revision_id: str
    understanding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider: str
    spec: TestSpec


class AITestSpecCompiler:
    def __init__(self, provider: ModelProvider, provider_name: str = "model-provider") -> None:
        self.provider = provider
        self.provider_name = provider_name

    def compile(self, understanding: UnderstandingArtifact) -> CompiledSpecArtifact:
        response = self.provider.generate(
            "test-spec",
            {"understanding": understanding.model_dump(mode="json")},
        )
        spec = TestSpec.model_validate(response)
        return CompiledSpecArtifact(
            requirement_revision_id=understanding.requirement_revision_id,
            understanding_hash=object_hash(understanding.model_dump(mode="json")),
            provider=self.provider_name,
            spec=spec,
        )


class CandidateTestCode(FrozenModel):
    test_id: str
    requirement_revision_id: str
    spec_id: str
    oracle_ids: tuple[str, ...]
    code: str
    code_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hash(self) -> CandidateTestCode:
        if text_hash(self.code) != self.code_hash:
            raise ValueError("candidate code hash mismatch")
        return self


class FreeTimeTestGenerator:
    def generate(
        self,
        compiled: CompiledSpecArtifact,
        *,
        free_minutes: int = 2,
        close_seconds: int = 120,
        expected: bool = True,
    ) -> CandidateTestCode:
        oracle_ids = tuple(
            oracle.id
            for case in compiled.spec.cases
            for oracle in case.oracles
        )
        if not oracle_ids:
            raise ValueError("generated test requires at least one traceable oracle")
        code = (
            "from examples.demo_app.main import calculate_free_time\n\n\n"
            "def test_generated_free_time_boundary() -> None:\n"
            f"    # Requirement: {compiled.requirement_revision_id}\n"
            f"    # Oracles: {', '.join(oracle_ids)}\n"
            f"    result = calculate_free_time({free_minutes}, {close_seconds})\n"
            f"    assert result.free_time_applied is {expected}\n"
            f"    assert result.free_seconds == {free_minutes * 60}\n"
            f"    assert result.close_seconds == {close_seconds}\n"
        )
        return CandidateTestCode(
            test_id="GENERATED-FREE-TIME-BOUNDARY",
            requirement_revision_id=compiled.requirement_revision_id,
            spec_id=compiled.spec.id,
            oracle_ids=oracle_ids,
            code=code,
            code_hash=text_hash(code),
        )


class CodeValidationResult(FrozenModel):
    valid: bool
    errors: tuple[str, ...]
    assertion_count: int = Field(ge=0)
    test_function_count: int = Field(ge=0)


class SafePythonTestValidator:
    forbidden_import_roots = frozenset({"requests", "httpx", "socket", "subprocess"})
    forbidden_calls = frozenset({"eval", "exec", "compile", "open", "sleep"})

    def validate(self, candidate: CandidateTestCode) -> CodeValidationResult:
        errors: list[str] = []
        try:
            tree = ast.parse(candidate.code)
        except SyntaxError as exc:
            return CodeValidationResult(
                valid=False,
                errors=(f"syntax error: {exc}",),
                assertion_count=0,
                test_function_count=0,
            )
        assertions = sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
        tests = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            for node in ast.walk(tree)
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
                blocked = roots & self.forbidden_import_roots
                if blocked:
                    errors.append(f"forbidden import: {sorted(blocked)}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in self.forbidden_import_roots:
                    errors.append(f"forbidden import: {root}")
            elif isinstance(node, ast.Call):
                name = call_name(node.func)
                if name in self.forbidden_calls or name.endswith(".sleep"):
                    errors.append(f"forbidden call: {name}")
            elif isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant):
                errors.append("constant assertion is not allowed")
        if assertions == 0:
            errors.append("candidate test contains no assertions")
        if tests == 0:
            errors.append("candidate code contains no test function")
        return CodeValidationResult(
            valid=not errors,
            errors=tuple(errors),
            assertion_count=assertions,
            test_function_count=tests,
        )


class ProofExecution(FrozenModel):
    phase: str
    return_code: int
    duration_ms: int = Field(ge=0)
    stdout: str
    stderr: str


class CandidateProofReport(FrozenModel):
    baseline: ProofExecution
    mutation: ProofExecution
    restored: ProofExecution
    mutation_killed: bool
    restored_hash_matches: bool
    passed: bool


class CandidateProofGate:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def verify(
        self,
        *,
        test_path: Path,
        mutation_path: Path,
        find: str,
        replace: str,
    ) -> CandidateProofReport:
        test_path = test_path.resolve()
        mutation_path = mutation_path.resolve()
        self._inside_repo(mutation_path)
        original = mutation_path.read_text(encoding="utf-8")
        if find == replace:
            raise ValueError("mutation must change source text")
        count = original.count(find)
        if count != 1:
            raise ValueError(f"mutation target must occur once, found {count}")
        original_hash = file_hash(mutation_path)
        baseline = self._run(test_path, "baseline")
        mutation: ProofExecution
        restored: ProofExecution
        try:
            mutation_path.write_text(original.replace(find, replace, 1), encoding="utf-8")
            mutation = self._run(test_path, "mutation")
        finally:
            mutation_path.write_text(original, encoding="utf-8")
        restored_hash_matches = file_hash(mutation_path) == original_hash
        restored = self._run(test_path, "restored")
        killed = baseline.return_code == 0 and mutation.return_code != 0
        passed = killed and restored.return_code == 0 and restored_hash_matches
        return CandidateProofReport(
            baseline=baseline,
            mutation=mutation,
            restored=restored,
            mutation_killed=killed,
            restored_hash_matches=restored_hash_matches,
            passed=passed,
        )

    def _run(self, test_path: Path, phase: str) -> ProofExecution:
        started = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-q"],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        return ProofExecution(
            phase=phase,
            return_code=completed.returncode,
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _inside_repo(self, path: Path) -> None:
        if not path.is_relative_to(self.repo_root):
            raise ValueError("mutation path must remain inside repository")


def call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def object_hash(value: dict[str, Any]) -> str:
    import json

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text_hash(encoded)


def text_hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
