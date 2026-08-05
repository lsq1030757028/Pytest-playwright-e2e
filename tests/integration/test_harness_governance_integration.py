from __future__ import annotations

import pytest

from test_workflow.harness import (
    ArtifactKind,
    ArtifactValidity,
    AssuranceLevel,
    AssuranceRouter,
    CampaignState,
    CampaignStateMachine,
    ChangeAction,
    ChangeEvent,
    ChangeImpactAnalyzer,
    ChangeSignals,
    ChangeType,
    ImpactEdge,
    ImpactGraph,
    ImpactNode,
    ProgressCalculator,
    SourceRevisionRegistry,
    SourceRole,
    TestCampaign,
)


def todo_graph() -> ImpactGraph:
    return ImpactGraph(
        nodes=(
            ImpactNode(artifact_id="req", kind=ArtifactKind.REQUIREMENT, completed=True),
            ImpactNode(artifact_id="oracle-clear", kind=ArtifactKind.ORACLE, completed=True),
            ImpactNode(artifact_id="spec-clear", kind=ArtifactKind.TEST_SPEC, completed=True),
            ImpactNode(artifact_id="test-clear", kind=ArtifactKind.TEST_ASSET, completed=True),
            ImpactNode(artifact_id="evidence-clear", kind=ArtifactKind.EVIDENCE, completed=True),
            ImpactNode(artifact_id="test-filter", kind=ArtifactKind.TEST_ASSET, completed=True),
        ),
        edges=(
            ImpactEdge(source="req", target="oracle-clear"),
            ImpactEdge(source="oracle-clear", target="spec-clear"),
            ImpactEdge(source="spec-clear", target="test-clear"),
            ImpactEdge(source="test-clear", target="evidence-clear"),
        ),
    )


def change(
    change_id: str,
    change_type: ChangeType,
    *,
    role: SourceRole = SourceRole.PRODUCT_OWNER,
    approved: bool = True,
    affected: tuple[str, ...] = ("oracle-clear",),
) -> ChangeEvent:
    return ChangeEvent(
        change_id=change_id,
        requirement_id="REQ-TODO-001",
        from_revision_id="REQ-TODO-001@v1",
        to_revision_id="REQ-TODO-001@v2",
        change_type=change_type,
        source_role=role,
        approved=approved,
        affected_refs=affected,
        summary=change_id,
    )


@pytest.mark.harness_integration
def test_todomvc_six_change_decisions_and_valid_progress() -> None:
    graph = todo_graph()
    analyzer = ChangeImpactAnalyzer()
    calculator = ProgressCalculator()

    clarification = analyzer.assess(
        change("clarification", ChangeType.CLARIFICATION),
        graph,
        AssuranceLevel.L1,
    )
    acceptance = analyzer.assess(
        change("acceptance", ChangeType.ACCEPTANCE_ADDITION),
        graph,
        AssuranceLevel.L1,
    )
    upgraded_level = AssuranceRouter().route(
        ChangeSignals(cross_service=True, change_type=ChangeType.SCOPE_EXPANSION)
    ).level
    expansion = analyzer.assess(
        change("tabs", ChangeType.SCOPE_EXPANSION, affected=("req",)),
        graph,
        AssuranceLevel.L1,
        upgraded_level,
    )
    oracle = analyzer.assess(
        change("oracle", ChangeType.ORACLE_CHANGE),
        graph,
        AssuranceLevel.L1,
    )
    unauthorized = SourceRevisionRegistry.authorize_change(
        change(
            "developer-suggestion",
            ChangeType.ORACLE_CHANGE,
            role=SourceRole.DEVELOPER,
        )
    )
    conflict = analyzer.assess(
        change("conflict", ChangeType.INVARIANT_CONFLICT),
        graph,
        AssuranceLevel.L1,
    )

    assert clarification.action == ChangeAction.RESUME
    assert not clarification.affected
    assert acceptance.action == ChangeAction.LOCAL_REPLAN
    assert acceptance.affected["test-clear"] == ArtifactValidity.REQUIRES_REVIEW
    assert expansion.action == ChangeAction.ASSURANCE_UPGRADE
    assert expansion.assurance_after == AssuranceLevel.L2
    assert oracle.affected["evidence-clear"] == ArtifactValidity.SUPERSEDED
    assert "test-filter" in oracle.unaffected
    assert unauthorized.approved is False
    assert conflict.action == ChangeAction.BLOCK
    assert conflict.assurance_after == AssuranceLevel.L3

    before = calculator.calculate(graph.nodes)
    after = calculator.calculate(graph.nodes, oracle.affected)
    assert before.raw_progress == after.raw_progress == 1
    assert after.valid_progress < before.valid_progress

    machine = CampaignStateMachine()
    campaign = TestCampaign(
        campaign_id="CAMPAIGN-TODO-GOLDEN",
        requirement_revision_id="REQ-TODO-001@v1",
        assurance_level=AssuranceLevel.L1,
        state=CampaignState.EXECUTING,
    )
    assessing = machine.transition(
        campaign,
        CampaignState.CHANGE_ASSESSMENT,
        change_id="conflict",
    )
    blocked = machine.transition(
        assessing,
        CampaignState.BLOCKED,
        blocked_reason=conflict.reason,
        assurance_level=conflict.assurance_after,
    )
    assert blocked.state == CampaignState.BLOCKED
    assert blocked.assurance_level == AssuranceLevel.L3
