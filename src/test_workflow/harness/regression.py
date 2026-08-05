from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .contracts import FrozenModel
from .governance import AssuranceLevel
from .intelligence import BusinessPriority


class TestAssetStatus(StrEnum):
    CANDIDATE = "candidate"
    BASELINE_VALIDATED = "baseline_validated"
    PROOF_VERIFIED = "proof_verified"
    REGRESSION = "regression"
    DEPRECATED = "deprecated"


class TestLayer(StrEnum):
    STATIC = "static"
    UNIT = "unit"
    API = "api"
    INTEGRATION = "integration"
    E2E = "e2e"
    PROBE = "probe"


class TestAssetRecord(FrozenModel):
    test_id: str
    status: TestAssetStatus = TestAssetStatus.CANDIDATE
    requirement_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    domain_tags: frozenset[str]
    layer: TestLayer
    priority: BusinessPriority
    duration_seconds: float = Field(default=1, ge=0)
    baseline_passed: bool = False
    mutation_killed: bool = False
    stability_runs: int = Field(default=0, ge=0)
    stability_passed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_stability(self) -> TestAssetRecord:
        if self.stability_passed > self.stability_runs:
            raise ValueError("stability_passed cannot exceed stability_runs")
        return self


class TestAssetRegistry:
    def __init__(self) -> None:
        self._items: dict[str, TestAssetRecord] = {}

    def put(self, record: TestAssetRecord) -> TestAssetRecord:
        existing = self._items.get(record.test_id)
        if existing and existing != record:
            raise ValueError(f"test asset {record.test_id!r} is immutable")
        self._items[record.test_id] = record
        return record

    def get(self, test_id: str) -> TestAssetRecord:
        return self._items[test_id]

    def promote(self, test_id: str, target: TestAssetStatus) -> TestAssetRecord:
        current = self.get(test_id)
        allowed = {
            TestAssetStatus.CANDIDATE: TestAssetStatus.BASELINE_VALIDATED,
            TestAssetStatus.BASELINE_VALIDATED: TestAssetStatus.PROOF_VERIFIED,
            TestAssetStatus.PROOF_VERIFIED: TestAssetStatus.REGRESSION,
            TestAssetStatus.REGRESSION: TestAssetStatus.DEPRECATED,
        }
        if allowed.get(current.status) != target:
            raise ValueError(f"illegal asset promotion: {current.status} -> {target}")
        if target == TestAssetStatus.BASELINE_VALIDATED and not current.baseline_passed:
            raise ValueError("baseline must pass before validation")
        if target == TestAssetStatus.PROOF_VERIFIED and not current.mutation_killed:
            raise ValueError("a target mutation must be killed before proof verification")
        if target == TestAssetStatus.REGRESSION and (
            current.stability_runs < 3
            or current.stability_passed != current.stability_runs
        ):
            raise ValueError("regression promotion requires at least three stable runs")
        updated = current.model_copy(update={"status": target})
        self._items[test_id] = updated
        return updated


class ImpactMapping(FrozenModel):
    change_ref: str
    test_id: str
    relation: str = "direct"


class RegressionGraph(FrozenModel):
    tests: tuple[TestAssetRecord, ...]
    mappings: tuple[ImpactMapping, ...]

    @model_validator(mode="after")
    def validate_mappings(self) -> RegressionGraph:
        test_ids = {item.test_id for item in self.tests}
        missing = {item.test_id for item in self.mappings} - test_ids
        if missing:
            raise ValueError(f"mappings reference unknown tests: {sorted(missing)}")
        return self


class RegressionSelection(FrozenModel):
    selected_test_ids: tuple[str, ...]
    reasons: dict[str, tuple[str, ...]]
    estimated_seconds: float = Field(ge=0)
    full_suite_seconds: float = Field(ge=0)
    reduction_ratio: float = Field(ge=0, le=1)
    omitted_critical_test_ids: tuple[str, ...]


class RegressionSelector:
    def select(
        self,
        graph: RegressionGraph,
        *,
        changed_refs: frozenset[str],
        assurance_level: AssuranceLevel,
    ) -> RegressionSelection:
        tests = {item.test_id: item for item in graph.tests}
        selected: set[str] = set()
        reasons: dict[str, set[str]] = {}

        for mapping in graph.mappings:
            if mapping.change_ref in changed_refs:
                selected.add(mapping.test_id)
                reasons.setdefault(mapping.test_id, set()).add(
                    f"{mapping.relation}:{mapping.change_ref}"
                )

        if assurance_level in {AssuranceLevel.L1, AssuranceLevel.L2, AssuranceLevel.L3}:
            for item in graph.tests:
                if "smoke" in item.domain_tags:
                    selected.add(item.test_id)
                    reasons.setdefault(item.test_id, set()).add("assurance:smoke")

        affected_domains = {
            tag
            for test_id in selected
            for tag in tests[test_id].domain_tags
            if tag != "smoke"
        }
        if assurance_level in {AssuranceLevel.L2, AssuranceLevel.L3}:
            for item in graph.tests:
                if affected_domains.intersection(item.domain_tags):
                    selected.add(item.test_id)
                    reasons.setdefault(item.test_id, set()).add("assurance:domain")

        if assurance_level == AssuranceLevel.L3:
            for item in graph.tests:
                if item.priority in {BusinessPriority.P0, BusinessPriority.P1}:
                    selected.add(item.test_id)
                    reasons.setdefault(item.test_id, set()).add("assurance:critical")

        full = sum(item.duration_seconds for item in graph.tests)
        estimated = sum(tests[test_id].duration_seconds for test_id in selected)
        critical_direct = {
            mapping.test_id
            for mapping in graph.mappings
            if mapping.change_ref in changed_refs
            and tests[mapping.test_id].priority == BusinessPriority.P0
        }
        omitted = tuple(sorted(critical_direct - selected))
        return RegressionSelection(
            selected_test_ids=tuple(sorted(selected)),
            reasons={key: tuple(sorted(value)) for key, value in sorted(reasons.items())},
            estimated_seconds=estimated,
            full_suite_seconds=full,
            reduction_ratio=(1 - estimated / full) if full else 0,
            omitted_critical_test_ids=omitted,
        )


class BenchmarkCase(FrozenModel):
    case_id: str
    expected_critical_tests: frozenset[str]
    expected_all_tests: frozenset[str]
    selected_tests: frozenset[str]
    defect_present: bool = False
    verdict_passed: bool = False
    execution_seconds: float = Field(default=0, ge=0)
    full_suite_seconds: float = Field(default=0, ge=0)


class BenchmarkReport(FrozenModel):
    case_count: int = Field(ge=0)
    critical_recall: float = Field(ge=0, le=1)
    overall_recall: float = Field(ge=0, le=1)
    false_green_count: int = Field(ge=0)
    average_reduction_ratio: float = Field(ge=0, le=1)
    passed: bool


class BenchmarkEvaluator:
    def evaluate(self, cases: tuple[BenchmarkCase, ...]) -> BenchmarkReport:
        expected_critical = sum(len(item.expected_critical_tests) for item in cases)
        selected_critical = sum(
            len(item.expected_critical_tests & item.selected_tests) for item in cases
        )
        expected_all = sum(len(item.expected_all_tests) for item in cases)
        selected_all = sum(len(item.expected_all_tests & item.selected_tests) for item in cases)
        false_green = sum(item.defect_present and item.verdict_passed for item in cases)
        reductions = [
            1 - item.execution_seconds / item.full_suite_seconds
            for item in cases
            if item.full_suite_seconds
        ]
        critical_recall = selected_critical / expected_critical if expected_critical else 1
        overall_recall = selected_all / expected_all if expected_all else 1
        average_reduction = sum(reductions) / len(reductions) if reductions else 0
        passed = critical_recall == 1 and false_green == 0
        return BenchmarkReport(
            case_count=len(cases),
            critical_recall=critical_recall,
            overall_recall=overall_recall,
            false_green_count=false_green,
            average_reduction_ratio=average_reduction,
            passed=passed,
        )
