from __future__ import annotations

import hashlib
from collections import Counter, defaultdict, deque
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from .artifacts import StoreExecutionContext
from .contracts import (
    ArtifactRef,
    ArtifactTypeRef,
    ArtifactValidity,
    CapabilityDescriptor,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    ContextLevel,
    ContextRequest,
    ExecutionBudget,
    FrozenModel,
    PermissionScope,
)


class SourceRole(StrEnum):
    DEVELOPER = "developer"
    QA = "qa"
    PRODUCT_OWNER = "product_owner"
    OPERATIONS = "operations"
    SYSTEM = "system"


class SourceStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChangeType(StrEnum):
    CLARIFICATION = "clarification"
    ACCEPTANCE_ADDITION = "acceptance_addition"
    ORACLE_CHANGE = "oracle_change"
    SCOPE_EXPANSION = "scope_expansion"
    SCOPE_REDUCTION = "scope_reduction"
    ENVIRONMENT_CHANGE = "environment_change"
    REPLACEMENT = "replacement"
    INVARIANT_CONFLICT = "invariant_conflict"


class ChangeAction(StrEnum):
    RESUME = "resume"
    LOCAL_REPLAN = "local_replan"
    ASSURANCE_UPGRADE = "assurance_upgrade"
    BLOCK = "block"
    SUPERSEDE = "supersede"


class AssuranceLevel(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    LE = "LE"


class CampaignState(StrEnum):
    RECEIVED = "received"
    TRIAGED = "triaged"
    CAMPAIGN_CREATED = "campaign_created"
    MODEL_SCOPE_READY = "model_scope_ready"
    PLANNED = "planned"
    ASSETS_READY = "assets_ready"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    GATED = "gated"
    VERIFIED = "verified"
    CHANGE_ASSESSMENT = "change_assessment"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class ArtifactKind(StrEnum):
    REQUIREMENT = "requirement"
    FACT = "fact"
    INVARIANT = "invariant"
    ORACLE = "oracle"
    TEST_SPEC = "test_spec"
    TEST_ASSET = "test_asset"
    ENVIRONMENT = "environment"
    EVIDENCE = "evidence"
    GATE = "gate"


class SourceRecord(FrozenModel):
    source_id: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    role: SourceRole
    locator: str | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: SourceStatus = SourceStatus.PROPOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RequirementRevision(FrozenModel):
    revision_id: str = Field(min_length=1, max_length=128)
    requirement_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_id: str
    parent_revision_id: str | None = None
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChangeEvent(FrozenModel):
    change_id: str = Field(min_length=1, max_length=128)
    requirement_id: str
    from_revision_id: str | None = None
    to_revision_id: str
    change_type: ChangeType
    source_role: SourceRole
    approved: bool = False
    affected_refs: tuple[str, ...] = ()
    risk_tags: frozenset[str] = frozenset()
    summary: str = Field(min_length=1)


class ChangeAuthorization(FrozenModel):
    approved: bool
    reason: str
    required_roles: frozenset[SourceRole]


class SourceRevisionRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, SourceRecord] = {}
        self._revisions: dict[str, RequirementRevision] = {}
        self._versions: dict[str, dict[int, str]] = defaultdict(dict)

    def register_source(
        self,
        *,
        source_id: str,
        source_type: str,
        role: SourceRole,
        content: str,
        locator: str | None = None,
        status: SourceStatus = SourceStatus.PROPOSED,
    ) -> SourceRecord:
        record = SourceRecord(
            source_id=source_id,
            source_type=source_type,
            role=role,
            locator=locator,
            content_hash=text_hash(content),
            status=status,
        )
        existing = self._sources.get(source_id)
        if existing and existing != record:
            raise ValueError(f"source {source_id!r} is immutable")
        self._sources[source_id] = record
        return record

    def add_revision(
        self,
        *,
        revision_id: str,
        requirement_id: str,
        version: int,
        content: str,
        source_id: str,
        parent_revision_id: str | None = None,
        approved: bool = False,
    ) -> RequirementRevision:
        if source_id not in self._sources:
            raise ValueError(f"unknown source {source_id!r}")
        if parent_revision_id and parent_revision_id not in self._revisions:
            raise ValueError(f"unknown parent revision {parent_revision_id!r}")
        if version in self._versions[requirement_id]:
            raise ValueError(f"requirement version already exists: {requirement_id}@v{version}")
        if parent_revision_id:
            parent = self._revisions[parent_revision_id]
            if parent.requirement_id != requirement_id or parent.version >= version:
                raise ValueError("parent revision must be an older version of the same requirement")
        revision = RequirementRevision(
            revision_id=revision_id,
            requirement_id=requirement_id,
            version=version,
            content_hash=text_hash(content),
            source_id=source_id,
            parent_revision_id=parent_revision_id,
            approved=approved,
        )
        if revision_id in self._revisions:
            raise ValueError(f"revision {revision_id!r} already exists")
        self._revisions[revision_id] = revision
        self._versions[requirement_id][version] = revision_id
        return revision

    def get_revision(self, revision_id: str) -> RequirementRevision:
        try:
            return self._revisions[revision_id]
        except KeyError as exc:
            raise KeyError(f"unknown revision {revision_id!r}") from exc

    def latest(self, requirement_id: str) -> RequirementRevision:
        versions = self._versions.get(requirement_id)
        if not versions:
            raise KeyError(f"unknown requirement {requirement_id!r}")
        return self._revisions[versions[max(versions)]]

    @staticmethod
    def authorize_change(event: ChangeEvent) -> ChangeAuthorization:
        required = authority_roles(event.change_type)
        approved = event.approved and event.source_role in required
        if approved:
            reason = "approved source has authority for this change type"
        elif not event.approved:
            reason = "change is proposed but not approved"
        else:
            reason = f"role {event.source_role} cannot approve {event.change_type}"
        return ChangeAuthorization(approved=approved, reason=reason, required_roles=required)


class ChangeSignals(FrozenModel):
    behavior_change: bool = True
    emergency: bool = False
    money: bool = False
    permissions: bool = False
    privacy: bool = False
    migration: bool = False
    destructive: bool = False
    irreversible: bool = False
    persistence: bool = False
    state_machine: bool = False
    idempotency: bool = False
    cross_service: bool = False
    public_api: bool = False
    observability_only: bool = False
    change_type: ChangeType | None = None
    candidate_level: AssuranceLevel | None = None


class AssuranceDecision(FrozenModel):
    level: AssuranceLevel
    policy_floor: AssuranceLevel
    reasons: tuple[str, ...]
    required_checks: tuple[str, ...]
    skipped_checks: tuple[str, ...]
    context_level: ContextLevel
    budget: ExecutionBudget
    risk_candidate_budget: int = Field(ge=0)
    loss_scenario_budget: int = Field(ge=0)
    mutation_budget: int = Field(ge=0)
    replay_runs: int = Field(ge=0)


class AssuranceRouter:
    def route(self, signals: ChangeSignals) -> AssuranceDecision:
        floor, reasons = self._floor(signals)
        if signals.emergency:
            return assurance_profile(
                AssuranceLevel.LE,
                policy_floor=floor,
                reasons=(*reasons, "emergency delivery path requested"),
            )
        candidate = signals.candidate_level or (AssuranceLevel.L1 if signals.behavior_change else AssuranceLevel.L0)
        level = max_assurance(floor, candidate)
        return assurance_profile(level, policy_floor=floor, reasons=reasons)

    @staticmethod
    def _floor(signals: ChangeSignals) -> tuple[AssuranceLevel, tuple[str, ...]]:
        critical = {
            "money": signals.money,
            "permissions": signals.permissions,
            "privacy": signals.privacy,
            "migration": signals.migration,
            "destructive": signals.destructive,
            "irreversible": signals.irreversible,
        }
        important = {
            "persistence": signals.persistence,
            "state_machine": signals.state_machine,
            "idempotency": signals.idempotency,
            "cross_service": signals.cross_service,
            "public_api": signals.public_api,
        }
        critical_hits = tuple(name for name, enabled in critical.items() if enabled)
        important_hits = tuple(name for name, enabled in important.items() if enabled)
        if critical_hits:
            return AssuranceLevel.L3, tuple(f"production-critical asset: {item}" for item in critical_hits)
        if important_hits or signals.change_type == ChangeType.SCOPE_EXPANSION:
            reasons = tuple(f"important behavior: {item}" for item in important_hits)
            if signals.change_type == ChangeType.SCOPE_EXPANSION:
                reasons = (*reasons, "requirement scope expanded")
            return AssuranceLevel.L2, reasons
        if not signals.behavior_change or signals.observability_only:
            return AssuranceLevel.L0, ("no product behavior change",)
        return AssuranceLevel.L1, ("ordinary reversible behavior change",)


class TestCampaign(FrozenModel):
    campaign_id: str
    version: int = Field(default=1, ge=1)
    requirement_revision_id: str
    assurance_level: AssuranceLevel
    state: CampaignState = CampaignState.RECEIVED
    frozen: bool = False
    blocked_reason: str | None = None
    change_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_campaign(self) -> TestCampaign:
        if self.state == CampaignState.BLOCKED and not self.blocked_reason:
            raise ValueError("blocked campaign requires a reason")
        if self.state != CampaignState.BLOCKED and self.blocked_reason:
            raise ValueError("only blocked campaign can carry blocked_reason")
        return self


class CampaignStateMachine:
    _allowed: dict[CampaignState, frozenset[CampaignState]] = {
        CampaignState.RECEIVED: frozenset({CampaignState.TRIAGED, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.TRIAGED: frozenset({CampaignState.CAMPAIGN_CREATED, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.CAMPAIGN_CREATED: frozenset({CampaignState.MODEL_SCOPE_READY, CampaignState.PLANNED, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.MODEL_SCOPE_READY: frozenset({CampaignState.PLANNED, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.PLANNED: frozenset({CampaignState.ASSETS_READY, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.ASSETS_READY: frozenset({CampaignState.EXECUTING, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.EXECUTING: frozenset({CampaignState.EVALUATING, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.EVALUATING: frozenset({CampaignState.GATED, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.GATED: frozenset({CampaignState.VERIFIED, CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.VERIFIED: frozenset({CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.CHANGE_ASSESSMENT: frozenset({CampaignState.EXECUTING, CampaignState.PLANNED, CampaignState.MODEL_SCOPE_READY, CampaignState.BLOCKED, CampaignState.SUPERSEDED}),
        CampaignState.BLOCKED: frozenset({CampaignState.CHANGE_ASSESSMENT}),
        CampaignState.SUPERSEDED: frozenset(),
    }

    def transition(
        self,
        campaign: TestCampaign,
        target: CampaignState,
        *,
        blocked_reason: str | None = None,
        change_id: str | None = None,
        assurance_level: AssuranceLevel | None = None,
        requirement_revision_id: str | None = None,
    ) -> TestCampaign:
        if target not in self._allowed[campaign.state]:
            raise ValueError(f"illegal campaign transition: {campaign.state} -> {target}")
        changes = campaign.change_ids
        if change_id and change_id not in changes:
            changes = (*changes, change_id)
        return TestCampaign(
            campaign_id=campaign.campaign_id,
            version=campaign.version + 1,
            requirement_revision_id=requirement_revision_id or campaign.requirement_revision_id,
            assurance_level=assurance_level or campaign.assurance_level,
            state=target,
            frozen=campaign.frozen or target == CampaignState.GATED,
            blocked_reason=blocked_reason if target == CampaignState.BLOCKED else None,
            change_ids=changes,
        )


class ImpactNode(FrozenModel):
    artifact_id: str
    kind: ArtifactKind
    validity: ArtifactValidity = ArtifactValidity.VALID
    weight: float = Field(default=1, gt=0)
    completed: bool = False


class ImpactEdge(FrozenModel):
    source: str
    target: str


class ImpactGraph(FrozenModel):
    nodes: tuple[ImpactNode, ...]
    edges: tuple[ImpactEdge, ...] = ()

    @model_validator(mode="after")
    def validate_graph(self) -> ImpactGraph:
        ids = [node.artifact_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("impact graph node ids must be unique")
        known = set(ids)
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("impact graph edge references an unknown node")
        return self

    def node_map(self) -> dict[str, ImpactNode]:
        return {node.artifact_id: node for node in self.nodes}

    def descendants(self, roots: tuple[str, ...]) -> frozenset[str]:
        children: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges:
            children[edge.source].add(edge.target)
        selected = set(roots)
        queue = deque(roots)
        while queue:
            current = queue.popleft()
            for child in children[current]:
                if child not in selected:
                    selected.add(child)
                    queue.append(child)
        return frozenset(selected)


class ImpactAssessment(FrozenModel):
    action: ChangeAction
    assurance_before: AssuranceLevel
    assurance_after: AssuranceLevel
    affected: dict[str, ArtifactValidity]
    unaffected: tuple[str, ...]
    reason: str


class ChangeImpactAnalyzer:
    def assess(
        self,
        event: ChangeEvent,
        graph: ImpactGraph,
        assurance_before: AssuranceLevel,
        assurance_after: AssuranceLevel | None = None,
    ) -> ImpactAssessment:
        node_map = graph.node_map()
        if event.change_type == ChangeType.CLARIFICATION:
            return ImpactAssessment(
                action=ChangeAction.RESUME,
                assurance_before=assurance_before,
                assurance_after=assurance_before,
                affected={},
                unaffected=tuple(sorted(node_map)),
                reason="clarification does not alter behavior or oracle",
            )
        if event.change_type == ChangeType.INVARIANT_CONFLICT:
            return ImpactAssessment(
                action=ChangeAction.BLOCK,
                assurance_before=assurance_before,
                assurance_after=max_assurance(assurance_before, AssuranceLevel.L3),
                affected={},
                unaffected=tuple(sorted(node_map)),
                reason="requirement conflicts with a production invariant",
            )

        roots = event.affected_refs or tuple(
            node.artifact_id for node in graph.nodes if node.kind == ArtifactKind.REQUIREMENT
        )
        unknown = sorted(set(roots) - set(node_map))
        if unknown:
            raise ValueError(f"unknown affected refs: {', '.join(unknown)}")
        selected = graph.descendants(roots)
        validity = self._validity(event.change_type, node_map, selected)
        after = assurance_after or assurance_before
        if event.change_type == ChangeType.REPLACEMENT:
            action = ChangeAction.SUPERSEDE
        elif assurance_rank(after) > assurance_rank(assurance_before):
            action = ChangeAction.ASSURANCE_UPGRADE
        else:
            action = ChangeAction.LOCAL_REPLAN
        return ImpactAssessment(
            action=action,
            assurance_before=assurance_before,
            assurance_after=after,
            affected=validity,
            unaffected=tuple(sorted(set(node_map) - set(validity))),
            reason=f"{event.change_type} invalidates only the reachable artifact subgraph",
        )

    @staticmethod
    def _validity(
        change_type: ChangeType,
        nodes: dict[str, ImpactNode],
        selected: frozenset[str],
    ) -> dict[str, ArtifactValidity]:
        result: dict[str, ArtifactValidity] = {}
        for artifact_id in sorted(selected):
            kind = nodes[artifact_id].kind
            if change_type == ChangeType.REPLACEMENT:
                result[artifact_id] = ArtifactValidity.SUPERSEDED
            elif change_type == ChangeType.ORACLE_CHANGE:
                result[artifact_id] = (
                    ArtifactValidity.SUPERSEDED
                    if kind in {ArtifactKind.EVIDENCE, ArtifactKind.GATE}
                    else ArtifactValidity.REQUIRES_REVIEW
                )
            elif change_type == ChangeType.ENVIRONMENT_CHANGE:
                result[artifact_id] = (
                    ArtifactValidity.REQUIRES_RERUN
                    if kind in {ArtifactKind.EVIDENCE, ArtifactKind.GATE}
                    else ArtifactValidity.REQUIRES_REVIEW
                )
            elif change_type == ChangeType.SCOPE_REDUCTION:
                result[artifact_id] = ArtifactValidity.HISTORICAL
            else:
                result[artifact_id] = (
                    ArtifactValidity.CONDITIONALLY_VALID
                    if kind == ArtifactKind.EVIDENCE
                    else ArtifactValidity.REQUIRES_REVIEW
                )
        return result


class ProgressReport(FrozenModel):
    raw_progress: float = Field(ge=0, le=1)
    valid_progress: float = Field(ge=0, le=1)
    total_weight: float = Field(ge=0)
    completed_weight: float = Field(ge=0)
    valid_weight: float = Field(ge=0)
    validity_counts: dict[str, int]


class ProgressCalculator:
    def calculate(
        self,
        nodes: tuple[ImpactNode, ...],
        overrides: dict[str, ArtifactValidity] | None = None,
    ) -> ProgressReport:
        overrides = overrides or {}
        total = sum(node.weight for node in nodes)
        completed = sum(node.weight for node in nodes if node.completed)
        valid = 0.0
        counts: Counter[str] = Counter()
        for node in nodes:
            validity = overrides.get(node.artifact_id, node.validity)
            counts[validity.value] += 1
            if node.completed:
                valid += node.weight * validity_factor(validity)
        return ProgressReport(
            raw_progress=completed / total if total else 0,
            valid_progress=valid / total if total else 0,
            total_weight=total,
            completed_weight=completed,
            valid_weight=valid,
            validity_counts=dict(sorted(counts.items())),
        )


def authority_roles(change_type: ChangeType) -> frozenset[SourceRole]:
    if change_type == ChangeType.CLARIFICATION:
        return frozenset({SourceRole.DEVELOPER, SourceRole.QA, SourceRole.PRODUCT_OWNER, SourceRole.SYSTEM})
    if change_type == ChangeType.ENVIRONMENT_CHANGE:
        return frozenset({SourceRole.OPERATIONS, SourceRole.QA, SourceRole.SYSTEM})
    return frozenset({SourceRole.PRODUCT_OWNER, SourceRole.SYSTEM})


def assurance_rank(level: AssuranceLevel) -> int:
    return {
        AssuranceLevel.L0: 0,
        AssuranceLevel.L1: 1,
        AssuranceLevel.L2: 2,
        AssuranceLevel.L3: 3,
        AssuranceLevel.LE: 4,
    }[level]


def max_assurance(left: AssuranceLevel, right: AssuranceLevel) -> AssuranceLevel:
    return left if assurance_rank(left) >= assurance_rank(right) else right


def assurance_profile(
    level: AssuranceLevel,
    *,
    policy_floor: AssuranceLevel,
    reasons: tuple[str, ...],
) -> AssuranceDecision:
    profiles: dict[AssuranceLevel, dict[str, Any]] = {
        AssuranceLevel.L0: {
            "required": ("lint", "collect", "affected_unit"),
            "skipped": ("business_model", "e2e", "mutation", "full_replay"),
            "context": ContextLevel.METADATA,
            "budget": ExecutionBudget(wall_time_seconds=180, artifact_bytes=2_000_000),
            "risk": 0,
            "loss": 0,
            "mutation": 0,
            "replay": 0,
        },
        AssuranceLevel.L1: {
            "required": ("affected_unit", "affected_api", "critical_e2e"),
            "skipped": ("deep_business_model", "mutation", "production_probe"),
            "context": ContextLevel.SUMMARY,
            "budget": ExecutionBudget(subprocesses=3, browser_sessions=1, wall_time_seconds=600, artifact_bytes=10_000_000),
            "risk": 3,
            "loss": 1,
            "mutation": 0,
            "replay": 1,
        },
        AssuranceLevel.L2: {
            "required": ("local_business_model", "unit_api", "critical_e2e", "targeted_replay", "targeted_mutation"),
            "skipped": ("full_production_probe",),
            "context": ContextLevel.FOCUSED,
            "budget": ExecutionBudget(model_calls=3, token_limit=30_000, subprocesses=8, browser_sessions=3, api_calls=20, wall_time_seconds=1800, artifact_bytes=50_000_000),
            "risk": 6,
            "loss": 3,
            "mutation": 3,
            "replay": 3,
        },
        AssuranceLevel.L3: {
            "required": ("production_invariants", "loss_scenarios", "multi_layer_tests", "mutation", "full_replay", "reconciliation", "rollback"),
            "skipped": (),
            "context": ContextLevel.DEEP,
            "budget": ExecutionBudget(model_calls=8, token_limit=100_000, subprocesses=20, browser_sessions=8, api_calls=100, wall_time_seconds=7200, artifact_bytes=200_000_000),
            "risk": 10,
            "loss": 6,
            "mutation": 8,
            "replay": 5,
        },
        AssuranceLevel.LE: {
            "required": ("minimum_safety", "canary", "strong_monitoring", "fast_rollback", "post_release_backfill"),
            "skipped": ("pre_release_full_regression",),
            "context": ContextLevel.FOCUSED,
            "budget": ExecutionBudget(model_calls=2, token_limit=20_000, subprocesses=5, browser_sessions=2, api_calls=20, wall_time_seconds=900, artifact_bytes=30_000_000),
            "risk": 5,
            "loss": 2,
            "mutation": 1,
            "replay": 1,
        },
    }
    value = profiles[level]
    return AssuranceDecision(
        level=level,
        policy_floor=policy_floor,
        reasons=reasons,
        required_checks=value["required"],
        skipped_checks=value["skipped"],
        context_level=value["context"],
        budget=value["budget"],
        risk_candidate_budget=value["risk"],
        loss_scenario_budget=value["loss"],
        mutation_budget=value["mutation"],
        replay_runs=value["replay"],
    )


def validity_factor(validity: ArtifactValidity) -> float:
    return {
        ArtifactValidity.VALID: 1.0,
        ArtifactValidity.CONDITIONALLY_VALID: 0.5,
        ArtifactValidity.REQUIRES_REVIEW: 0.0,
        ArtifactValidity.REQUIRES_RERUN: 0.0,
        ArtifactValidity.SUPERSEDED: 0.0,
        ArtifactValidity.INVALID: 0.0,
        ArtifactValidity.HISTORICAL: 0.0,
    }[validity]


def text_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


class AssuranceRouteCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="assurance.route",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="ChangeSignals", schema_version=1),),
            output_types=(ArtifactTypeRef(name="AssuranceDecision", schema_version=1),),
            default_context=ContextRequest(level=ContextLevel.SUMMARY),
            required_permissions=PermissionScope(
                read=frozenset({"artifacts/change-signals/*"}),
                write=frozenset({"artifacts/assurance/*"}),
            ),
            timeout_seconds=2,
        )

    def execute(self, request: CapabilityRequest, context: StoreExecutionContext) -> CapabilityResult:
        if len(request.input_artifacts) != 1:
            return CapabilityResult(
                request_id=request.request_id,
                status=CapabilityResultStatus.FAILED,
                error="assurance.route requires one ChangeSignals artifact",
            )
        try:
            signals = ChangeSignals.model_validate(context.read_artifact(request.input_artifacts[0]))
            decision = AssuranceRouter().route(signals)
            ref = context.write_artifact(
                artifact_id=f"assurance/{request.request_id}",
                artifact_type="AssuranceDecision",
                schema_version=1,
                content=decision.model_dump(mode="json"),
                created_by=self.descriptor.ref,
                source_revisions={"signals": request.input_artifacts[0].artifact_id},
            )
            return CapabilityResult(
                request_id=request.request_id,
                status=CapabilityResultStatus.SUCCESS,
                artifacts=(ref,),
            )
        except Exception as exc:
            return CapabilityResult(
                request_id=request.request_id,
                status=CapabilityResultStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )


def register_governance_capabilities(registry: Any) -> None:
    registry.register(AssuranceRouteCapability())
