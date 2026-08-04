from __future__ import annotations

import pytest

from test_workflow.harness import AssuranceLevel
from test_workflow.harness.intelligence import (
    BusinessPriority,
    HiddenUnderstandingEvaluator,
    IncrementalBusinessCompiler,
    MockModelProvider,
    ReleaseAction,
    RiskPromotionEngine,
)


@pytest.mark.harness_integration
def test_todomvc_incremental_understanding_covers_p0_without_false_blocker() -> None:
    provider = MockModelProvider(
        {
            "business-understanding": {
                "model": {
                    "model_id": "todo-cleanup-model",
                    "assets": [
                        {
                            "asset_id": "todo-data",
                            "name": "Todo data",
                            "asset_type": "user_data",
                            "priority": "P0",
                            "recoverability": "difficult",
                        }
                    ],
                    "roles": [],
                    "transitions": [],
                    "facts": [
                        {
                            "fact_id": "FACT-CLEAR-001",
                            "statement": "clear completed deletes completed items",
                            "source_ref": "REQ-TODO@v2",
                            "confidence": 1,
                        }
                    ],
                    "assumptions": [],
                    "unknowns": [],
                    "invariants": [
                        {
                            "invariant_id": "INV-DATA-001",
                            "statement": "active items remain after clearing completed",
                            "category": "data_integrity",
                            "priority": "P0",
                            "asset_refs": ["todo-data"],
                            "source_ref": "approved-rule",
                            "testable_expression": "active_after == active_before",
                        },
                        {
                            "invariant_id": "INV-PERSIST-001",
                            "statement": "saved items remain after reload",
                            "category": "reliability",
                            "priority": "P1",
                            "asset_refs": ["todo-data"],
                            "source_ref": "approved-rule",
                            "testable_expression": "items_after_reload == items_before_reload",
                        },
                    ],
                },
                "loss_scenarios": [
                    {
                        "scenario_id": "LOSS-DATA-001",
                        "asset_ref": "todo-data",
                        "trigger": "clear completed",
                        "failure_mode": "active items are deleted",
                        "loss": "user data loss",
                        "priority": "P0",
                        "affected_scope": "active items",
                        "recoverability": "difficult",
                        "test_obligations": ["clear completed preserves active items"],
                    },
                    {
                        "scenario_id": "LOSS-PERSIST-001",
                        "asset_ref": "todo-data",
                        "trigger": "reload",
                        "failure_mode": "saved items disappear",
                        "loss": "user work lost",
                        "priority": "P0",
                        "affected_scope": "all saved items",
                        "recoverability": "difficult",
                        "test_obligations": ["new item persists after reload"],
                    },
                    {
                        "scenario_id": "LOW-COSMETIC",
                        "asset_ref": "todo-data",
                        "trigger": "render",
                        "failure_mode": "counter spacing differs",
                        "loss": "minor presentation issue",
                        "priority": "P4",
                        "affected_scope": "visual only",
                        "recoverability": "easy",
                        "test_obligations": ["counter is readable"],
                    },
                ],
                "source_conflicts": [],
            }
        }
    )
    artifact = IncrementalBusinessCompiler(provider).compile(
        requirement_revision_id="REQ-TODO@v2",
        assurance_level=AssuranceLevel.L2,
        requirement_text="clear completed must preserve active items and data must persist",
        scope=("todo.cleanup", "todo.persistence"),
    )
    evaluation = HiddenUnderstandingEvaluator().evaluate(
        artifact,
        required_invariant_ids=frozenset({"INV-DATA-001", "INV-PERSIST-001"}),
        required_p0_scenarios=frozenset({"LOSS-DATA-001", "LOSS-PERSIST-001"}),
    )

    assert artifact.model.scope == ("todo.cleanup", "todo.persistence")
    assert len(artifact.loss_scenarios) == 3
    assert evaluation.passed is True
    assert evaluation.p0_recall == 1
    assert evaluation.false_blockers == ()
    assert all(
        RiskPromotionEngine().decide(item).release_action == ReleaseAction.RECORD
        for item in artifact.loss_scenarios
        if item.priority == BusinessPriority.P0
    )
