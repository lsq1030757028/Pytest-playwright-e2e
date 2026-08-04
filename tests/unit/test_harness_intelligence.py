from __future__ import annotations

import pytest

from test_workflow.harness.intelligence import (
    BusinessAsset,
    BusinessPriority,
    EvidenceLevel,
    HiddenUnderstandingEvaluator,
    IncrementalBusinessCompiler,
    InvariantCategory,
    LossScenario,
    MockModelProvider,
    ProductionInvariant,
    ReleaseAction,
    RiskPromotionEngine,
    RiskStatus,
    merge_invariants,
)
from test_workflow.harness import AssuranceLevel


def invariant() -> ProductionInvariant:
    return ProductionInvariant(
        invariant_id="INV-DATA-001",
        statement="clearing completed items preserves active items",
        category=InvariantCategory.DATA_INTEGRITY,
        priority=BusinessPriority.P0,
        asset_refs=("todo-data",),
        source_ref="approved-rule",
        testable_expression="active_items_after == active_items_before",
    )


def scenario(priority: BusinessPriority = BusinessPriority.P0) -> LossScenario:
    return LossScenario(
        scenario_id="LOSS-DATA-001",
        asset_ref="todo-data",
        trigger="clear completed",
        failure_mode="active items are deleted",
        loss="user data loss",
        priority=priority,
        affected_scope="all active items",
        recoverability="difficult",
        test_obligations=("clear completed preserves active items",),
    )


def provider() -> MockModelProvider:
    return MockModelProvider(
        {
            "business-understanding": {
                "model": {
                    "model_id": "todo-local",
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
                    "facts": [],
                    "assumptions": [],
                    "unknowns": [],
                    "invariants": [],
                },
                "loss_scenarios": [scenario().model_dump(mode="json")],
                "source_conflicts": [],
            }
        }
    )


def test_business_model_rejects_unknown_invariant_asset() -> None:
    bad = invariant().model_copy(update={"asset_refs": ("missing",)})
    response = provider().responses["business-understanding"]
    response["model"]["invariants"] = [bad.model_dump(mode="json")]
    with pytest.raises(ValueError, match="unknown assets"):
        IncrementalBusinessCompiler(provider()).compile(
            requirement_revision_id="REQ@v1",
            assurance_level=AssuranceLevel.L2,
            requirement_text="clear completed",
            scope=("todo.cleanup",),
        )


def test_incremental_compiler_preserves_known_invariant_and_scope() -> None:
    model_provider = provider()
    artifact = IncrementalBusinessCompiler(model_provider).compile(
        requirement_revision_id="REQ@v1",
        assurance_level=AssuranceLevel.L2,
        requirement_text="clear completed",
        scope=("todo.cleanup",),
        known_invariants=(invariant(),),
    )
    assert artifact.model.scope == ("todo.cleanup",)
    assert artifact.model.invariants == (invariant(),)
    assert model_provider.calls[0][1]["scope"] == ["todo.cleanup"]


def test_l1_limits_loss_scenario_budget() -> None:
    model_provider = provider()
    response = model_provider.responses["business-understanding"]
    response["loss_scenarios"] = [
        scenario(BusinessPriority.P2).model_copy(update={"scenario_id": "P2"}).model_dump(mode="json"),
        scenario(BusinessPriority.P0).model_copy(update={"scenario_id": "P0"}).model_dump(mode="json"),
    ]
    artifact = IncrementalBusinessCompiler(model_provider).compile(
        requirement_revision_id="REQ@v1",
        assurance_level=AssuranceLevel.L1,
        requirement_text="change",
        scope=("todo.cleanup",),
    )
    assert [item.scenario_id for item in artifact.loss_scenarios] == ["P0"]


def test_risk_promotion_requires_reproduction_before_blocking() -> None:
    engine = RiskPromotionEngine()
    candidate = engine.decide(scenario())
    supported = engine.decide(scenario(), causal_path_confirmed=True)
    reproduced = engine.decide(scenario(), reproduced=True)

    assert candidate.release_action == ReleaseAction.RECORD
    assert supported.release_action == ReleaseAction.INVESTIGATE
    assert reproduced.release_action == ReleaseAction.BLOCK
    assert reproduced.status == RiskStatus.REPRODUCED
    assert reproduced.evidence_level == EvidenceLevel.E3


def test_controlled_risk_no_longer_blocks_release() -> None:
    decision = RiskPromotionEngine().decide(
        scenario(),
        independent_replay=True,
        control_added=True,
    )
    assert decision.status == RiskStatus.CONTROLLED
    assert decision.release_action == ReleaseAction.RECORD


def test_p1_reproduced_risk_requires_canary() -> None:
    decision = RiskPromotionEngine().decide(
        scenario(BusinessPriority.P1),
        reproduced=True,
    )
    assert decision.release_action == ReleaseAction.CANARY_REQUIRED


def test_merge_invariants_rejects_conflicting_generated_definition() -> None:
    generated = invariant().model_copy(update={"statement": "different"})
    with pytest.raises(ValueError, match="conflicts"):
        merge_invariants((invariant(),), (generated,))


def test_hidden_evaluator_detects_missing_p0_and_invariant() -> None:
    artifact = IncrementalBusinessCompiler(provider()).compile(
        requirement_revision_id="REQ@v1",
        assurance_level=AssuranceLevel.L2,
        requirement_text="change",
        scope=("todo.cleanup",),
    )
    result = HiddenUnderstandingEvaluator().evaluate(
        artifact,
        required_invariant_ids=frozenset({"INV-DATA-001"}),
        required_p0_scenarios=frozenset({"LOSS-DATA-001", "LOSS-PERSIST-001"}),
    )
    assert result.passed is False
    assert result.missing_invariant_ids == ("INV-DATA-001",)
    assert result.p0_recall == 0.5
