from __future__ import annotations

import pytest

from test_workflow.harness import AssuranceLevel
from test_workflow.harness.intelligence import BusinessPriority
from test_workflow.harness.regression import (
    BenchmarkCase,
    BenchmarkEvaluator,
    ImpactMapping,
    RegressionGraph,
    RegressionSelector,
    TestAssetRecord,
    TestAssetRegistry,
    TestAssetStatus,
    TestLayer,
)


def asset(
    test_id: str,
    *,
    priority: BusinessPriority = BusinessPriority.P2,
    tags: frozenset[str] = frozenset({"todo"}),
    duration: float = 1,
    baseline: bool = True,
    mutation: bool = True,
    runs: int = 3,
    passed: int = 3,
) -> TestAssetRecord:
    return TestAssetRecord(
        test_id=test_id,
        requirement_refs=("REQ-TODO",),
        source_refs=("todo.py",),
        domain_tags=tags,
        layer=TestLayer.UNIT,
        priority=priority,
        duration_seconds=duration,
        baseline_passed=baseline,
        mutation_killed=mutation,
        stability_runs=runs,
        stability_passed=passed,
    )


def test_asset_promotion_requires_baseline_mutation_and_stability() -> None:
    registry = TestAssetRegistry()
    registry.put(asset("test-clear", baseline=False))
    with pytest.raises(ValueError, match="baseline"):
        registry.promote("test-clear", TestAssetStatus.BASELINE_VALIDATED)

    registry = TestAssetRegistry()
    registry.put(asset("test-clear"))
    registry.promote("test-clear", TestAssetStatus.BASELINE_VALIDATED)
    registry.promote("test-clear", TestAssetStatus.PROOF_VERIFIED)
    promoted = registry.promote("test-clear", TestAssetStatus.REGRESSION)
    assert promoted.status == TestAssetStatus.REGRESSION


def test_asset_registry_is_immutable() -> None:
    registry = TestAssetRegistry()
    registry.put(asset("test-clear"))
    with pytest.raises(ValueError, match="immutable"):
        registry.put(asset("test-clear", duration=2))


def graph() -> RegressionGraph:
    return RegressionGraph(
        tests=(
            asset(
                "test-clear",
                priority=BusinessPriority.P0,
                tags=frozenset({"todo", "cleanup"}),
                duration=10,
            ),
            asset(
                "test-persist",
                priority=BusinessPriority.P0,
                tags=frozenset({"todo", "persistence"}),
                duration=20,
            ),
            asset(
                "test-filter",
                tags=frozenset({"todo", "filter"}),
                duration=5,
            ),
            asset(
                "test-smoke",
                tags=frozenset({"smoke"}),
                duration=2,
            ),
            asset(
                "test-unrelated",
                tags=frozenset({"account"}),
                duration=30,
            ),
        ),
        mappings=(
            ImpactMapping(change_ref="todo.cleanup", test_id="test-clear"),
            ImpactMapping(change_ref="todo.persistence", test_id="test-persist"),
            ImpactMapping(change_ref="todo.filter", test_id="test-filter"),
        ),
    )


def test_l1_selects_direct_and_smoke_only() -> None:
    selected = RegressionSelector().select(
        graph(),
        changed_refs=frozenset({"todo.cleanup"}),
        assurance_level=AssuranceLevel.L1,
    )
    assert selected.selected_test_ids == ("test-clear", "test-smoke")
    assert selected.omitted_critical_test_ids == ()
    assert selected.reduction_ratio > 0.8


def test_l2_expands_to_affected_domain_but_not_unrelated_domain() -> None:
    selected = RegressionSelector().select(
        graph(),
        changed_refs=frozenset({"todo.cleanup"}),
        assurance_level=AssuranceLevel.L2,
    )
    assert "test-clear" in selected.selected_test_ids
    assert "test-filter" in selected.selected_test_ids
    assert "test-persist" in selected.selected_test_ids
    assert "test-unrelated" not in selected.selected_test_ids


def test_l3_adds_all_critical_tests() -> None:
    selected = RegressionSelector().select(
        graph(),
        changed_refs=frozenset({"todo.filter"}),
        assurance_level=AssuranceLevel.L3,
    )
    assert "test-clear" in selected.selected_test_ids
    assert "test-persist" in selected.selected_test_ids


def test_benchmark_fails_on_false_green_even_with_full_recall() -> None:
    report = BenchmarkEvaluator().evaluate(
        (
            BenchmarkCase(
                case_id="false-green",
                expected_critical_tests=frozenset({"critical"}),
                expected_all_tests=frozenset({"critical"}),
                selected_tests=frozenset({"critical"}),
                defect_present=True,
                verdict_passed=True,
                execution_seconds=5,
                full_suite_seconds=10,
            ),
        )
    )
    assert report.critical_recall == 1
    assert report.false_green_count == 1
    assert report.passed is False


def test_benchmark_reports_recall_and_reduction() -> None:
    report = BenchmarkEvaluator().evaluate(
        (
            BenchmarkCase(
                case_id="one",
                expected_critical_tests=frozenset({"critical"}),
                expected_all_tests=frozenset({"critical", "optional"}),
                selected_tests=frozenset({"critical"}),
                execution_seconds=4,
                full_suite_seconds=10,
            ),
        )
    )
    assert report.critical_recall == 1
    assert report.overall_recall == 0.5
    assert report.average_reduction_ratio == 0.6
    assert report.passed is True
