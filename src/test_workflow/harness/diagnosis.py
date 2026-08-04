from __future__ import annotations

import hashlib
import subprocess
import sys
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from .contracts import FrozenModel


class EvidenceType(StrEnum):
    TRACEBACK = "traceback"
    BROWSER_TRACE = "browser_trace"
    DOM = "dom"
    NETWORK = "network"
    API = "api"
    STATE_PROBE = "state_probe"
    ENVIRONMENT = "environment"
    REQUIREMENT = "requirement"
    HISTORY = "history"


class FailureCategory(StrEnum):
    TEST_DEFECT = "test_defect"
    PRODUCT_DEFECT = "product_defect"
    ENVIRONMENT = "environment"
    REQUIREMENT_CONFLICT = "requirement_conflict"
    FLAKY = "flaky"
    UNKNOWN = "unknown"


class RepairKind(StrEnum):
    LOCATOR = "locator"
    SYNCHRONIZATION = "synchronization"
    FIXTURE = "fixture"
    TEST_DATA = "test_data"
    CLEANUP = "cleanup"
    SYNTAX = "syntax"


class EvidenceItem(FrozenModel):
    evidence_id: str
    evidence_type: EvidenceType
    source: str
    summary: str
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)


class FailureEvidence(FrozenModel):
    run_id: str
    items: tuple[EvidenceItem, ...]
    oracle_confirmed: bool = True
    previous_outcomes: tuple[str, ...] = ()


class DiagnosisResult(FrozenModel):
    category: FailureCategory
    confidence: float = Field(ge=0, le=1)
    root_cause: str
    evidence_refs: tuple[str, ...]
    auto_repair_allowed: bool
    recommended_scope: tuple[str, ...]


class RuleFirstDiagnoser:
    def diagnose(self, evidence: FailureEvidence) -> DiagnosisResult:
        summaries = "\n".join(item.summary.lower() for item in evidence.items)
        refs = tuple(item.evidence_id for item in evidence.items)
        environment_items = [
            item
            for item in evidence.items
            if item.evidence_type == EvidenceType.ENVIRONMENT
        ]
        if any(item.attributes.get("healthy") is False for item in environment_items):
            return DiagnosisResult(
                category=FailureCategory.ENVIRONMENT,
                confidence=0.99,
                root_cause="environment precondition or dependency is unhealthy",
                evidence_refs=refs,
                auto_repair_allowed=False,
                recommended_scope=("environment-preflight",),
            )
        if not evidence.oracle_confirmed or "requirement_invariant_conflict" in summaries:
            return DiagnosisResult(
                category=FailureCategory.REQUIREMENT_CONFLICT,
                confidence=0.98,
                root_cause="the expected behavior is unconfirmed or conflicts with an invariant",
                evidence_refs=refs,
                auto_repair_allowed=False,
                recommended_scope=("requirement-review",),
            )
        if "strict mode violation" in summaries or "locator" in summaries and "not found" in summaries:
            return DiagnosisResult(
                category=FailureCategory.TEST_DEFECT,
                confidence=0.95,
                root_cause="test locator no longer identifies one stable element",
                evidence_refs=refs,
                auto_repair_allowed=True,
                recommended_scope=("failed-test", "smoke"),
            )
        if "fixture" in summaries and ("not found" in summaries or "conflict" in summaries):
            return DiagnosisResult(
                category=FailureCategory.TEST_DEFECT,
                confidence=0.93,
                root_cause="fixture dependency or test data setup is invalid",
                evidence_refs=refs,
                auto_repair_allowed=True,
                recommended_scope=("failed-test", "fixture-unit"),
            )
        state_items = [
            item
            for item in evidence.items
            if item.evidence_type == EvidenceType.STATE_PROBE
        ]
        if any(item.attributes.get("oracle_mismatch") is True for item in state_items):
            return DiagnosisResult(
                category=FailureCategory.PRODUCT_DEFECT,
                confidence=0.97,
                root_cause="independent state probe contradicts a confirmed oracle",
                evidence_refs=refs,
                auto_repair_allowed=False,
                recommended_scope=("domain-regression", "mutation-proof"),
            )
        outcomes = set(evidence.previous_outcomes)
        if {"pass", "fail"}.issubset(outcomes) and (
            "timeout" in summaries or "intermittent" in summaries
        ):
            return DiagnosisResult(
                category=FailureCategory.FLAKY,
                confidence=0.85,
                root_cause="the same revisions produced inconsistent outcomes",
                evidence_refs=refs,
                auto_repair_allowed=False,
                recommended_scope=("stability-replay",),
            )
        return DiagnosisResult(
            category=FailureCategory.UNKNOWN,
            confidence=0.4,
            root_cause="deterministic rules cannot classify the available evidence",
            evidence_refs=refs,
            auto_repair_allowed=False,
            recommended_scope=("evidence-enrichment",),
        )


class RepairProposal(FrozenModel):
    repair_id: str
    kind: RepairKind
    file_path: str
    find: str = Field(min_length=1)
    replace: str
    evidence_refs: tuple[str, ...]
    rationale: str

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("repair file path must be safe and relative")
        return value


class RepairValidation(FrozenModel):
    allowed: bool
    reasons: tuple[str, ...]


class SafeRepairValidator:
    allowed_roots = ("tests/", "src/test_workflow/adapters/")
    forbidden_additions = ("time.sleep(", "sleep(", "@pytest.mark.flaky", "reruns=")

    def validate(self, proposal: RepairProposal) -> RepairValidation:
        reasons: list[str] = []
        if not proposal.file_path.startswith(self.allowed_roots):
            reasons.append("repair is outside the allowed test-engineering scope")
        if proposal.find == proposal.replace:
            reasons.append("repair is a no-op")
        if proposal.find.count("\n") > 20 or proposal.replace.count("\n") > 20:
            reasons.append("repair exceeds the bounded patch size")
        if "assert" in proposal.find and "assert" not in proposal.replace:
            reasons.append("repair removes an assertion")
        if any(item in proposal.replace for item in self.forbidden_additions):
            reasons.append("repair introduces forbidden sleep or retry behavior")
        lowered = f"{proposal.find}\n{proposal.replace}".lower()
        if "oracle" in lowered or "expected" in lowered and proposal.kind != RepairKind.TEST_DATA:
            reasons.append("repair may modify a confirmed oracle")
        return RepairValidation(allowed=not reasons, reasons=tuple(reasons))


class RepairVerification(FrozenModel):
    before_return_code: int
    after_return_code: int
    patch_applied: bool
    passed: bool
    stdout: str
    stderr: str


class CandidateRepairRunner:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def verify(self, proposal: RepairProposal, test_path: Path) -> RepairVerification:
        validation = SafeRepairValidator().validate(proposal)
        if not validation.allowed:
            raise ValueError("; ".join(validation.reasons))
        target = (self.workspace_root / proposal.file_path).resolve()
        if not target.is_relative_to(self.workspace_root) or not target.exists():
            raise ValueError("repair target must exist inside the workspace")
        original = target.read_text(encoding="utf-8")
        count = original.count(proposal.find)
        if count != 1:
            raise ValueError(f"repair target must occur once, found {count}")
        before = self._run(test_path)
        target.write_text(original.replace(proposal.find, proposal.replace, 1), encoding="utf-8")
        after = self._run(test_path)
        passed = before.returncode != 0 and after.returncode == 0
        if not passed:
            target.write_text(original, encoding="utf-8")
        return RepairVerification(
            before_return_code=before.returncode,
            after_return_code=after.returncode,
            patch_applied=passed,
            passed=passed,
            stdout=after.stdout,
            stderr=after.stderr,
        )

    def _run(self, test_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-q"],
            cwd=self.workspace_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )


def evidence_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
