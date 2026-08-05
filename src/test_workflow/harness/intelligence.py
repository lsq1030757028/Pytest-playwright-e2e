from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, model_validator

from .contracts import FrozenModel
from .governance import AssuranceLevel


class BusinessPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class EvidenceLevel(StrEnum):
    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"


class RiskStatus(StrEnum):
    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    REPRODUCED = "reproduced"
    PROVEN = "proven"
    CONTROLLED = "controlled"


class ReleaseAction(StrEnum):
    RECORD = "record"
    INVESTIGATE = "investigate"
    WARN = "warn"
    CANARY_REQUIRED = "canary_required"
    BLOCK = "block"


class InvariantCategory(StrEnum):
    MONEY = "money"
    DATA_INTEGRITY = "data_integrity"
    AUTHORIZATION = "authorization"
    IDEMPOTENCY = "idempotency"
    STATE_MACHINE = "state_machine"
    AUDIT = "audit"
    RECOVERY = "recovery"
    RELIABILITY = "reliability"
    REQUIREMENT = "requirement"


class BusinessAsset(FrozenModel):
    asset_id: str
    name: str
    asset_type: str
    priority: BusinessPriority
    recoverability: str = "reversible"


class BusinessRole(FrozenModel):
    role_id: str
    name: str
    permissions: frozenset[str] = frozenset()


class StateTransition(FrozenModel):
    transition_id: str
    source: str
    target: str
    trigger: str
    guards: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()


class BusinessFact(FrozenModel):
    fact_id: str
    statement: str
    source_ref: str
    confidence: float = Field(ge=0, le=1)


class BusinessAssumption(FrozenModel):
    assumption_id: str
    statement: str
    basis: str
    confirmation_required: bool = True


class BusinessUnknown(FrozenModel):
    unknown_id: str
    question: str
    blocks_oracle: bool = False


class ProductionInvariant(FrozenModel):
    invariant_id: str
    statement: str
    category: InvariantCategory
    priority: BusinessPriority
    asset_refs: tuple[str, ...]
    source_ref: str
    testable_expression: str


class BusinessModel(FrozenModel):
    model_id: str
    scope: tuple[str, ...]
    assets: tuple[BusinessAsset, ...]
    roles: tuple[BusinessRole, ...] = ()
    transitions: tuple[StateTransition, ...] = ()
    facts: tuple[BusinessFact, ...] = ()
    assumptions: tuple[BusinessAssumption, ...] = ()
    unknowns: tuple[BusinessUnknown, ...] = ()
    invariants: tuple[ProductionInvariant, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> BusinessModel:
        asset_ids = {item.asset_id for item in self.assets}
        for invariant in self.invariants:
            missing = set(invariant.asset_refs) - asset_ids
            if missing:
                raise ValueError(
                    f"invariant {invariant.invariant_id} references unknown assets: "
                    f"{sorted(missing)}"
                )
        return self


class LossScenario(FrozenModel):
    scenario_id: str
    asset_ref: str
    trigger: str
    failure_mode: str
    loss: str
    priority: BusinessPriority
    affected_scope: str
    recoverability: str
    control_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    counter_evidence_refs: tuple[str, ...] = ()
    test_obligations: tuple[str, ...]
    evidence_level: EvidenceLevel = EvidenceLevel.E0
    status: RiskStatus = RiskStatus.CANDIDATE


class RiskDecision(FrozenModel):
    scenario_id: str
    status: RiskStatus
    evidence_level: EvidenceLevel
    release_action: ReleaseAction
    reason: str


class RiskPromotionEngine:
    def decide(
        self,
        scenario: LossScenario,
        *,
        causal_path_confirmed: bool = False,
        reproduced: bool = False,
        independent_replay: bool = False,
        control_added: bool = False,
    ) -> RiskDecision:
        if control_added and independent_replay:
            status = RiskStatus.CONTROLLED
            level = EvidenceLevel.E4
        elif independent_replay:
            status = RiskStatus.PROVEN
            level = EvidenceLevel.E4
        elif reproduced:
            status = RiskStatus.REPRODUCED
            level = EvidenceLevel.E3
        elif causal_path_confirmed:
            status = RiskStatus.SUPPORTED
            level = EvidenceLevel.E2
        elif scenario.evidence_refs:
            status = RiskStatus.CANDIDATE
            level = EvidenceLevel.E1
        else:
            status = RiskStatus.CANDIDATE
            level = EvidenceLevel.E0
        action, reason = release_decision(scenario.priority, level, status)
        return RiskDecision(
            scenario_id=scenario.scenario_id,
            status=status,
            evidence_level=level,
            release_action=action,
            reason=reason,
        )


class UnderstandingArtifact(FrozenModel):
    requirement_revision_id: str
    assurance_level: AssuranceLevel
    model: BusinessModel
    loss_scenarios: tuple[LossScenario, ...]
    source_conflicts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_scenario_assets(self) -> UnderstandingArtifact:
        asset_ids = {item.asset_id for item in self.model.assets}
        missing = {
            item.asset_ref
            for item in self.loss_scenarios
            if item.asset_ref not in asset_ids
        }
        if missing:
            raise ValueError(f"loss scenarios reference unknown assets: {sorted(missing)}")
        return self


@runtime_checkable
class ModelProvider(Protocol):
    def generate(self, task: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class MockModelProvider:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def generate(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((task, payload))
        try:
            return self.responses[task]
        except KeyError as exc:
            raise KeyError(f"no mock response for task {task!r}") from exc


class IncrementalBusinessCompiler:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def compile(
        self,
        *,
        requirement_revision_id: str,
        assurance_level: AssuranceLevel,
        requirement_text: str,
        scope: tuple[str, ...],
        known_invariants: tuple[ProductionInvariant, ...] = (),
    ) -> UnderstandingArtifact:
        if not scope:
            raise ValueError("incremental business scope cannot be empty")
        response = self.provider.generate(
            "business-understanding",
            {
                "requirement_revision_id": requirement_revision_id,
                "requirement_text": requirement_text,
                "scope": list(scope),
                "known_invariants": [item.model_dump(mode="json") for item in known_invariants],
            },
        )
        model_payload = dict(response.get("model", {}))
        model_payload["scope"] = list(scope)
        generated_invariants = tuple(
            ProductionInvariant.model_validate(item)
            for item in model_payload.pop("invariants", [])
        )
        merged_invariants = merge_invariants(known_invariants, generated_invariants)
        model = BusinessModel.model_validate(
            {**model_payload, "invariants": [item.model_dump(mode="json") for item in merged_invariants]}
        )
        scenarios = tuple(
            LossScenario.model_validate(item)
            for item in response.get("loss_scenarios", [])
        )
        budget = loss_scenario_limit(assurance_level)
        scenarios = tuple(sorted(scenarios, key=scenario_sort_key)[:budget])
        return UnderstandingArtifact(
            requirement_revision_id=requirement_revision_id,
            assurance_level=assurance_level,
            model=model,
            loss_scenarios=scenarios,
            source_conflicts=tuple(response.get("source_conflicts", [])),
        )


class UnderstandingEvaluation(FrozenModel):
    passed: bool
    missing_invariant_ids: tuple[str, ...]
    undeclared_oracle_assumptions: tuple[str, ...]
    false_blockers: tuple[str, ...]
    p0_recall: float = Field(ge=0, le=1)


class HiddenUnderstandingEvaluator:
    def evaluate(
        self,
        artifact: UnderstandingArtifact,
        *,
        required_invariant_ids: frozenset[str],
        required_p0_scenarios: frozenset[str],
        approved_blockers: frozenset[str] = frozenset(),
    ) -> UnderstandingEvaluation:
        present_invariants = {item.invariant_id for item in artifact.model.invariants}
        present_p0 = {
            item.scenario_id
            for item in artifact.loss_scenarios
            if item.priority == BusinessPriority.P0
        }
        missing = tuple(sorted(required_invariant_ids - present_invariants))
        undeclared = tuple(
            sorted(
                item.assumption_id
                for item in artifact.model.assumptions
                if item.confirmation_required
                and any(item.assumption_id in invariant.testable_expression for invariant in artifact.model.invariants)
            )
        )
        proposed_blockers = {
            item.scenario_id
            for item in artifact.loss_scenarios
            if RiskPromotionEngine()
            .decide(item)
            .release_action
            == ReleaseAction.BLOCK
        }
        false_blockers = tuple(sorted(proposed_blockers - approved_blockers))
        p0_recall = (
            len(required_p0_scenarios & present_p0) / len(required_p0_scenarios)
            if required_p0_scenarios
            else 1.0
        )
        passed = not missing and not undeclared and not false_blockers and p0_recall == 1
        return UnderstandingEvaluation(
            passed=passed,
            missing_invariant_ids=missing,
            undeclared_oracle_assumptions=undeclared,
            false_blockers=false_blockers,
            p0_recall=p0_recall,
        )


def merge_invariants(
    known: tuple[ProductionInvariant, ...],
    generated: tuple[ProductionInvariant, ...],
) -> tuple[ProductionInvariant, ...]:
    result = {item.invariant_id: item for item in known}
    for item in generated:
        existing = result.get(item.invariant_id)
        if existing and existing != item:
            raise ValueError(f"generated invariant conflicts with known invariant {item.invariant_id}")
        result[item.invariant_id] = item
    return tuple(result[key] for key in sorted(result))


def loss_scenario_limit(level: AssuranceLevel) -> int:
    return {
        AssuranceLevel.L0: 0,
        AssuranceLevel.L1: 1,
        AssuranceLevel.L2: 3,
        AssuranceLevel.L3: 6,
        AssuranceLevel.LE: 2,
    }[level]


def scenario_sort_key(item: LossScenario) -> tuple[int, str]:
    priority = {
        BusinessPriority.P0: 0,
        BusinessPriority.P1: 1,
        BusinessPriority.P2: 2,
        BusinessPriority.P3: 3,
        BusinessPriority.P4: 4,
    }[item.priority]
    return priority, item.scenario_id


def release_decision(
    priority: BusinessPriority,
    evidence: EvidenceLevel,
    status: RiskStatus,
) -> tuple[ReleaseAction, str]:
    if status == RiskStatus.CONTROLLED:
        return ReleaseAction.RECORD, "risk has an independently verified control"
    if priority == BusinessPriority.P0 and evidence in {EvidenceLevel.E3, EvidenceLevel.E4}:
        return ReleaseAction.BLOCK, "reproduced or proven P0 business loss"
    if priority == BusinessPriority.P0 and evidence == EvidenceLevel.E2:
        return ReleaseAction.INVESTIGATE, "credible P0 causal path requires resolution"
    if priority == BusinessPriority.P1 and evidence in {EvidenceLevel.E3, EvidenceLevel.E4}:
        return ReleaseAction.CANARY_REQUIRED, "reproduced P1 risk requires guarded rollout"
    if priority in {BusinessPriority.P2, BusinessPriority.P3} and evidence in {
        EvidenceLevel.E3,
        EvidenceLevel.E4,
    }:
        return ReleaseAction.WARN, "confirmed non-critical defect"
    return ReleaseAction.RECORD, "candidate risk has insufficient evidence to block"
