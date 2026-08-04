from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .contracts import FrozenModel
from .diagnosis import DiagnosisResult, FailureCategory
from .generation import CandidateProofReport, CodeValidationResult, CompiledSpecArtifact
from .governance import AssuranceDecision
from .intelligence import UnderstandingEvaluation
from .regression import BenchmarkReport, RegressionSelection


class VerdictStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class AgentVerdict(FrozenModel):
    requirement_revision_id: str
    status: VerdictStatus
    assurance_level: str
    understanding_valid: bool
    spec_valid: bool
    generated_code_valid: bool
    baseline: str
    negative_control: str
    restored: str
    negative_control_diagnosis: FailureCategory
    selected_test_ids: tuple[str, ...]
    critical_recall: float = Field(ge=0, le=1)
    false_green_count: int = Field(ge=0)
    blockers: tuple[str, ...] = ()


class VerdictBuilder:
    def build(
        self,
        *,
        assurance: AssuranceDecision,
        understanding: UnderstandingEvaluation,
        compiled_spec: CompiledSpecArtifact,
        code_validation: CodeValidationResult,
        proof: CandidateProofReport,
        negative_control_diagnosis: DiagnosisResult,
        regression: RegressionSelection,
        benchmark: BenchmarkReport,
    ) -> AgentVerdict:
        blockers: list[str] = []
        if not understanding.passed:
            blockers.append("business understanding hidden evaluation failed")
        if not code_validation.valid:
            blockers.append("generated code validation failed")
        if not proof.passed:
            blockers.append("generated test did not prove GREEN-RED-GREEN")
        if negative_control_diagnosis.category != FailureCategory.PRODUCT_DEFECT:
            blockers.append("negative control was not recognized as a product defect")
        if regression.omitted_critical_test_ids:
            blockers.append("critical regression tests were omitted")
        if not benchmark.passed:
            blockers.append("benchmark quality thresholds failed")
        status = VerdictStatus.PASS if not blockers else VerdictStatus.BLOCKED
        return AgentVerdict(
            requirement_revision_id=compiled_spec.requirement_revision_id,
            status=status,
            assurance_level=assurance.level.value,
            understanding_valid=understanding.passed,
            spec_valid=True,
            generated_code_valid=code_validation.valid,
            baseline="PASS" if proof.baseline.return_code == 0 else "FAIL",
            negative_control="FAIL" if proof.mutation.return_code != 0 else "PASS",
            restored="PASS" if proof.restored.return_code == 0 else "FAIL",
            negative_control_diagnosis=negative_control_diagnosis.category,
            selected_test_ids=regression.selected_test_ids,
            critical_recall=benchmark.critical_recall,
            false_green_count=benchmark.false_green_count,
            blockers=tuple(blockers),
        )
