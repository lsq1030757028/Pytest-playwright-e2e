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
    SourceStatus,
    TestCampaign,
)


def test_source_registry_is_immutable_and_versions_require_valid_parent() -> None:
    registry = SourceRevisionRegistry()
    registry.register_source(
        source_id="source-1",
        source_type="conversation",
        role=SourceRole.PRODUCT_OWNER,
        content="initial",
        status=SourceStatus.APPROVED,
    )
    first = registry.add_revision(
        revision_id="REQ-1@v1",
        requirement_id="REQ-1",
        version=1,
        content="initial",
        source_id="source-1",
        approved=True,
    )
    second = registry.add_revision(
        revision_id="REQ-1@v2",
        requirement_id="REQ-1",
        version=2,
        content="expanded",
        source_id="source-1",
        parent_revision_id=first.revision_id,
        approved=True,
    )

    assert registry.latest("REQ-1") == second
    with pytest.raises(ValueError, match="immutable"):
        registry.register_source(
            source_id="source-1",
            source_type="conversation",
            role=SourceRole.PRODUCT_OWNER,
            content="changed",
        )
    with pytest.raises(ValueError, match="already exists"):
        registry.add_revision(
            revision_id="REQ-1@v2-duplicate",
            requirement_id="REQ-1",
            version=2,
            content="duplicate",
            source_id="source-1",
        )


def test_change_authority_rejects_developer_oracle_change() -> None:
    event = ChangeEvent(
        change_id="change-1",
        requirement_id="REQ-1",
        to_revision_id="REQ-1@v2",
        change_type=ChangeType.ORACLE_CHANGE,
        source_role=SourceRole.DEVELOPER,
        approved=True,
        summary="change expected result",
    )
    authorization = SourceRevisionRegistry.authorize_change(event)
    assert authorization.approved is False
    assert SourceRole.PRODUCT_OWNER in authorization.required_roles


def test_change_authority_accepts_product_owner_oracle_change() -> None:
    event = ChangeEvent(
        change_id="change-2",
        requirement_id="REQ-1",
        to_revision_id="REQ-1@v2",
        change_type=ChangeType.ORACLE_CHANGE,
        source_role=SourceRole.PRODUCT_OWNER,
        approved=True,
        summary="approved expected result",
    )
    assert SourceRevisionRegistry.authorize_change(event).approved is True


@pytest.mark.parametrize(
    ("signals", "expected"),
    [
        (ChangeSignals(behavior_change=False), AssuranceLevel.L0),
        (ChangeSignals(), AssuranceLevel.L1),
        (ChangeSignals(persistence=True), AssuranceLevel.L2),
        (ChangeSignals(money=True), AssuranceLevel.L3),
        (ChangeSignals(money=True, emergency=True), AssuranceLevel.LE),
    ],
)
def test_assurance_router_applies_deterministic_floors(
    signals: ChangeSignals,
    expected: AssuranceLevel,
) -> None:
    decision = AssuranceRouter().route(signals)
    assert decision.level == expected


def test_model_candidate_cannot_lower_policy_floor() -> None:
    decision = AssuranceRouter().route(
        ChangeSignals(migration=True, candidate_level=AssuranceLevel.L0)
    )
    assert decision.level == AssuranceLevel.L3
    assert decision.policy_floor == AssuranceLevel.L3
    assert "mutation" in decision.required_checks


def test_campaign_rejects_illegal_transition_and_freezes_at_gate() -> None:
    machine = CampaignStateMachine()
    campaign = TestCampaign(
        campaign_id="CAMPAIGN-1",
        requirement_revision_id="REQ-1@v1",
        assurance_level=AssuranceLevel.L1,
    )
    with pytest.raises(ValueError, match="illegal"):
        machine.transition(campaign, CampaignState.EXECUTING)

    campaign = machine.transition(campaign, CampaignState.TRIAGED)
    campaign = machine.transition(campaign, CampaignState.CAMPAIGN_CREATED)
    campaign = machine.transition(campaign, CampaignState.PLANNED)
    campaign = machine.transition(campaign, CampaignState.ASSETS_READY)
    campaign = machine.transition(campaign, CampaignState.EXECUTING)
    campaign = machine.transition(campaign, CampaignState.EVALUATING)
    campaign = machine.transition(campaign, CampaignState.GATED)

    assert campaign.frozen is True
    assert campaign.version == 8


def test_any_active_campaign_can_enter_change_assessment_and_block() -> None:
    machine = CampaignStateMachine()
    campaign = TestCampaign(
        campaign_id="CAMPAIGN-1",
        requirement_revision_id="REQ-1@v1",
        assurance_level=AssuranceLevel.L2,
        state=CampaignState.EXECUTING,
    )
    assessing = machine.transition(
        campaign,
        CampaignState.CHANGE_ASSESSMENT,
        change_id="change-1",
    )
    blocked = machine.transition(
        assessing,
        CampaignState.BLOCKED,
        blocked_reason="requirement/invariant conflict",
    )
    assert blocked.state == CampaignState.BLOCKED
    assert blocked.change_ids == ("change-1",)


def graph() -> ImpactGraph:
    return ImpactGraph(
        nodes=(
            ImpactNode(
                artifact_id="requirement",
                kind=ArtifactKind.REQUIREMENT,
                completed=True,
                weight=1,
            ),
            ImpactNode(
                artifact_id="oracle",
                kind=ArtifactKind.ORACLE,
                completed=True,
                weight=2,
            ),
            ImpactNode(
                artifact_id="test",
                kind=ArtifactKind.TEST_ASSET,
                completed=True,
                weight=3,
            ),
            ImpactNode(
                artifact_id="evidence",
                kind=ArtifactKind.EVIDENCE,
                completed=True,
                weight=4,
            ),
            ImpactNode(
                artifact_id="unrelated",
                kind=ArtifactKind.TEST_ASSET,
                completed=True,
                weight=5,
            ),
        ),
        edges=(
            ImpactEdge(source="requirement", target="oracle"),
            ImpactEdge(source="oracle", target="test"),
            ImpactEdge(source="test", target="evidence"),
        ),
    )


def event(change_type: ChangeType, affected=("oracle",)) -> ChangeEvent:
    return ChangeEvent(
        change_id=f"change-{change_type}",
        requirement_id="REQ-1",
        from_revision_id="REQ-1@v1",
        to_revision_id="REQ-1@v2",
        change_type=change_type,
        source_role=SourceRole.PRODUCT_OWNER,
        approved=True,
        affected_refs=affected,
        summary="change",
    )


def test_clarification_keeps_all_assets_valid() -> None:
    assessment = ChangeImpactAnalyzer().assess(
        event(ChangeType.CLARIFICATION),
        graph(),
        AssuranceLevel.L1,
    )
    assert assessment.action == ChangeAction.RESUME
    assert not assessment.affected
    assert len(assessment.unaffected) == 5


def test_oracle_change_only_invalidates_reachable_subgraph() -> None:
    assessment = ChangeImpactAnalyzer().assess(
        event(ChangeType.ORACLE_CHANGE),
        graph(),
        AssuranceLevel.L1,
    )
    assert assessment.affected == {
        "evidence": ArtifactValidity.SUPERSEDED,
        "oracle": ArtifactValidity.REQUIRES_REVIEW,
        "test": ArtifactValidity.REQUIRES_REVIEW,
    }
    assert "unrelated" in assessment.unaffected
    assert "requirement" in assessment.unaffected


def test_progress_separates_raw_work_from_current_valid_work() -> None:
    value = graph()
    before = ProgressCalculator().calculate(value.nodes)
    assessment = ChangeImpactAnalyzer().assess(
        event(ChangeType.ORACLE_CHANGE),
        value,
        AssuranceLevel.L1,
    )
    after = ProgressCalculator().calculate(value.nodes, assessment.affected)

    assert before.raw_progress == 1
    assert before.valid_progress == 1
    assert after.raw_progress == 1
    assert after.valid_progress == pytest.approx(0.4)
