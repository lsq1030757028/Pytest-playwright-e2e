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
    TestLayer,
)


def test_asset(
    test_id: str,
    tags: frozenset[str],
    priority: BusinessPriority,
    duration: float,
) -> TestAssetRecord:
    return TestAssetRecord(
        test_id=test_id,
        requirement_refs=("REQ-TODO",),
        source_refs=("todo",),
        domain_tags=tags,
        layer=TestLayer.E2E,
        priority=priority,
        duration_seconds=duration,
        baseline_passed=True,
        mutation_killed=True,
        stability_runs=3,
        stability_passed=3,
    )


@pytest.mark.harness_integration
def test_todomvc_regression_selection_keeps_critical_recall_and_reduces_time() -> None:
    graph = RegressionGraph(
        tests=(
            test_asset("clear", frozenset({"todo", "cleanup"}), BusinessPriority.P0, 20),
            test_asset("persist", frozenset({"todo", "persistence"}), BusinessPriority.P0, 20),
            test_asset("filter", frozenset({"todo", "filter"}), BusinessPriority.P2, 10),
            test_asset("smoke", frozenset({"smoke"}), BusinessPriority.P2, 5),
            test_asset("account", frozenset({"account"}), BusinessPriority.P1, 45),
        ),
        mappings=(
            ImpactMapping(change_ref="todo.cleanup", test_id="clear"),
            ImpactMapping(change_ref="todo.persistence", test_id="persist"),
            ImpactMapping(change_ref="todo.filter", test_id="filter"),
            ImpactMapping(change_ref="account.profile", test_id="account"),
        ),
    )
    cleanup = RegressionSelector().select(
        graph,
        changed_refs=frozenset({"todo.cleanup"}),
        assurance_level=AssuranceLevel.L1,
    )
    persistence = RegressionSelector().select(
        graph,
        changed_refs=frozenset({"todo.persistence"}),
        assurance_level=AssuranceLevel.L1,
    )
    report = BenchmarkEvaluator().evaluate(
        (
            BenchmarkCase(
                case_id="cleanup",
                expected_critical_tests=frozenset({"clear"}),
                expected_all_tests=frozenset({"clear", "smoke"}),
                selected_tests=frozenset(cleanup.selected_test_ids),
                defect_present=True,
                verdict_passed=False,
                execution_seconds=cleanup.estimated_seconds,
                full_suite_seconds=cleanup.full_suite_seconds,
            ),
            BenchmarkCase(
                case_id="persistence",
                expected_critical_tests=frozenset({"persist"}),
                expected_all_tests=frozenset({"persist", "smoke"}),
                selected_tests=frozenset(persistence.selected_test_ids),
                defect_present=True,
                verdict_passed=False,
                execution_seconds=persistence.estimated_seconds,
                full_suite_seconds=persistence.full_suite_seconds,
            ),
        )
    )

    assert cleanup.omitted_critical_test_ids == ()
    assert persistence.omitted_critical_test_ids == ()
    assert report.critical_recall == 1
    assert report.overall_recall == 1
    assert report.false_green_count == 0
    assert report.average_reduction_ratio >= 0.7
    assert report.passed is True
