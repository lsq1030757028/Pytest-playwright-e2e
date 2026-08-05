from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .canonical import canonical_sha256
from .models import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    CompatibilityContext,
    CompatibilityDescriptor,
    CreatorType,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    NamespaceScopeKind,
    PrincipalContext,
    PrincipalType,
    PromotionRequest,
    Provenance,
    ReadMode,
    RetentionPolicy,
    StateEvent,
    TransformationKind,
)
from .policy import (
    evaluate_effective_read,
    evaluate_permission,
    validate_promotion,
    validate_transition,
)
from .reference import DeterministicMemoryReference

SPEC_REF = "SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0"
APPROVAL_REF = "APPROVAL-M1A-MEMORY-CONTRACTS-NAMESPACES-SPEC@1.0.0"
MANDATE_REF = "MANDATE-AUTONOMY-M1-M3@1.0.0"
CAMPAIGN_ID = "m1a-runtime-contract-proof-v1"
FIXED_NOW = datetime(2026, 8, 5, 13, 0, tzinfo=UTC)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScenarioResult(FrozenModel):
    scenario_id: str = Field(pattern=r"^M1A-RC-[0-9]{3}$")
    title: str
    passed: bool
    observed: str
    expected: str
    error_code: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ProofMetrics(FrozenModel):
    total: int
    passed: int
    failed: int
    critical_false_green: int
    unauthorized_namespace_actions: int
    unauthorized_promotion_actions: int
    stale_write_overwrites: int
    forgotten_content_reads: int


class ContractProofReport(FrozenModel):
    schema_version: str = "1.0.0"
    campaign_id: str
    spec_ref: str
    approval_ref: str
    mandate_ref: str
    code_sha: str
    results: tuple[ScenarioResult, ...]
    metrics: ProofMetrics
    verdict: str
    semantic_digest: str

    def core_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"semantic_digest"})


class ReplayResult(FrozenModel):
    schema_version: str = "1.0.0"
    campaign_id: str
    passed: bool
    expected_semantic_digest: str
    replay_semantic_digest: str
    verified_artifacts: tuple[str, ...]
    error: str | None = None


class ProofIntegrityError(RuntimeError):
    pass


def run_contract_proof(output_dir: Path, *, code_sha: str = "local") -> ContractProofReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = _execute_scenarios()
    metrics = ProofMetrics(
        total=len(results),
        passed=sum(result.passed for result in results),
        failed=sum(not result.passed for result in results),
        critical_false_green=sum(
            (not result.passed and result.observed == result.expected) for result in results
        ),
        unauthorized_namespace_actions=(
            0
            if results[1].passed
            and results[2].passed
            and results[11].passed
            and results[12].passed
            else 1
        ),
        unauthorized_promotion_actions=(
            0 if results[4].passed and results[14].passed else 1
        ),
        stale_write_overwrites=0 if results[6].passed else 1,
        forgotten_content_reads=0 if results[8].passed else 1,
    )
    verdict = "PASS" if metrics.failed == 0 and metrics.critical_false_green == 0 else "FAIL"
    core = {
        "schema_version": "1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "spec_ref": SPEC_REF,
        "approval_ref": APPROVAL_REF,
        "mandate_ref": MANDATE_REF,
        "code_sha": code_sha,
        "results": [result.model_dump(mode="json") for result in results],
        "metrics": metrics.model_dump(mode="json"),
        "verdict": verdict,
    }
    report = ContractProofReport(**core, semantic_digest=canonical_sha256(core))
    report_path = output_dir / "contract-report.json"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path = output_dir / "contract-report.md"
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    replay_manifest = {
        "schema_version": "1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "spec_ref": SPEC_REF,
        "code_sha": code_sha,
        "expected_semantic_digest": report.semantic_digest,
        "scenario_ids": [result.scenario_id for result in results],
    }
    replay_path = output_dir / "replay-manifest.json"
    replay_path.write_text(json.dumps(replay_manifest, indent=2, sort_keys=True), encoding="utf-8")
    artifact_files = (report_path, markdown_path, replay_path)
    manifest = {
        "schema_version": "1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "semantic_digest": report.semantic_digest,
        "artifacts": {path.name: _file_sha256(path) for path in artifact_files},
    }
    (output_dir / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def replay_contract_proof(output_dir: Path) -> ReplayResult:
    try:
        manifest = json.loads((output_dir / "artifact-manifest.json").read_text(encoding="utf-8"))
        replay_manifest = json.loads(
            (output_dir / "replay-manifest.json").read_text(encoding="utf-8")
        )
        report = ContractProofReport.model_validate_json(
            (output_dir / "contract-report.json").read_text(encoding="utf-8")
        )
        verified: list[str] = []
        for name, expected_digest in manifest["artifacts"].items():
            path = output_dir / name
            actual_digest = _file_sha256(path)
            if actual_digest != expected_digest:
                raise ProofIntegrityError(f"artifact digest mismatch: {name}")
            verified.append(name)
        if canonical_sha256(report.core_payload()) != report.semantic_digest:
            raise ProofIntegrityError("report semantic digest mismatch")
        if replay_manifest["expected_semantic_digest"] != report.semantic_digest:
            raise ProofIntegrityError("replay manifest does not bind the report digest")
        rerun = _execute_scenarios()
        replay_core = report.core_payload()
        replay_core["results"] = [result.model_dump(mode="json") for result in rerun]
        replay_metrics = ProofMetrics(
            total=len(rerun),
            passed=sum(result.passed for result in rerun),
            failed=sum(not result.passed for result in rerun),
            critical_false_green=sum(
                (not result.passed and result.observed == result.expected) for result in rerun
            ),
            unauthorized_namespace_actions=(
                0
                if rerun[1].passed
                and rerun[2].passed
                and rerun[11].passed
                and rerun[12].passed
                else 1
            ),
            unauthorized_promotion_actions=(
                0 if rerun[4].passed and rerun[14].passed else 1
            ),
            stale_write_overwrites=0 if rerun[6].passed else 1,
            forgotten_content_reads=0 if rerun[8].passed else 1,
        )
        replay_core["metrics"] = replay_metrics.model_dump(mode="json")
        replay_core["verdict"] = (
            "PASS"
            if replay_metrics.failed == 0 and replay_metrics.critical_false_green == 0
            else "FAIL"
        )
        replay_digest = canonical_sha256(replay_core)
        if replay_digest != report.semantic_digest:
            raise ProofIntegrityError("independent replay semantic drift")
        result = ReplayResult(
            campaign_id=CAMPAIGN_ID,
            passed=True,
            expected_semantic_digest=report.semantic_digest,
            replay_semantic_digest=replay_digest,
            verified_artifacts=tuple(sorted(verified)),
        )
    except (OSError, KeyError, ValueError, ValidationError, ProofIntegrityError) as exc:
        expected = "unknown"
        try:
            expected = json.loads(
                (output_dir / "replay-manifest.json").read_text(encoding="utf-8")
            ).get("expected_semantic_digest", "unknown")
        except (OSError, ValueError):
            pass
        result = ReplayResult(
            campaign_id=CAMPAIGN_ID,
            passed=False,
            expected_semantic_digest=expected,
            replay_semantic_digest="unavailable",
            verified_artifacts=(),
            error=str(exc),
        )
    (output_dir / "replay-result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    return result


def _execute_scenarios() -> tuple[ScenarioResult, ...]:
    scenarios: tuple[Callable[[], ScenarioResult], ...] = (
        _hash_stability,
        _cross_project_denied,
        _deny_override,
        _provenance_rejected,
        _candidate_promotion_denied,
        _verified_promotion_allowed,
        _stale_cas_conflict,
        _idempotency_payload_mismatch,
        _forgotten_content_unavailable,
        _embedded_code_rejected,
        _deep_immutability_enforced,
        _campaign_scope_denied,
        _expired_delegation_denied,
        _version_incompatibility_filtered,
        _promoter_spoof_denied,
    )
    return tuple(scenario() for scenario in scenarios)


def _hash_stability() -> ScenarioResult:
    left = canonical_sha256({"b": 2, "a": {"z": 3, "y": 4}})
    right = canonical_sha256({"a": {"y": 4, "z": 3}, "b": 2})
    passed = left == right
    return _result(1, "Canonical hash stability", passed, str(passed), "True", hashes=[left, right])


def _cross_project_denied() -> ScenarioResult:
    namespace, _, _, _ = _fixture()
    outsider = PrincipalContext(
        principal_id="agent-outsider",
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id="project-2",
        agent_id="agent-outsider",
        role_ids=("OWNER",),
    )
    decision = evaluate_permission(
        actor=outsider,
        namespace=namespace,
        operation=AccessOperation.READ_CONTENT,
        relevance_score=1.0,
    )
    passed = decision.error_code is ErrorCode.NAMESPACE_DENIED
    return _result(
        2,
        "Cross-project namespace denial",
        passed,
        decision.error_code.value if decision.error_code else decision.decision.value,
        ErrorCode.NAMESPACE_DENIED.value,
        error_code=decision.error_code,
    )


def _deny_override() -> ScenarioResult:
    namespace, owner, _, _ = _fixture()
    entries = (
        AclEntry(
            rule_id="allow",
            effect=AclEffect.ALLOW,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id=owner.principal_id,
            operations=(AccessOperation.READ_CONTENT,),
            namespace=namespace,
        ),
        AclEntry(
            rule_id="deny",
            effect=AclEffect.DENY,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id=owner.principal_id,
            operations=(AccessOperation.READ_CONTENT,),
            namespace=namespace,
        ),
    )
    decision = evaluate_permission(
        actor=owner,
        namespace=namespace,
        operation=AccessOperation.READ_CONTENT,
        acl_entries=entries,
    )
    passed = decision.decision is Decision.DENY and decision.matched_rule_ids == ("deny",)
    return _result(3, "DENY overrides ALLOW", passed, decision.decision.value, "DENY")


def _provenance_rejected() -> ScenarioResult:
    _, owner, revision, acl = _fixture()
    store = DeterministicMemoryReference(initial_acl=acl)
    outcome = store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="proof-provenance",
    )
    passed = outcome.error_code is ErrorCode.PROVENANCE_MISSING and not store.list_audit_events()
    return _result(
        4,
        "Missing provenance rejection",
        passed,
        outcome.error_code.value if outcome.error_code else outcome.decision.value,
        ErrorCode.PROVENANCE_MISSING.value,
        error_code=outcome.error_code,
    )


def _candidate_promotion_denied() -> ScenarioResult:
    namespace, owner, revision, _ = _fixture()
    permission = evaluate_permission(
        actor=owner, namespace=namespace, operation=AccessOperation.PROMOTE
    )
    request = _promotion_request(owner, revision)
    decision = validate_promotion(
        actor=owner,
        revision=revision,
        state=LifecycleState.CANDIDATE,
        request=request,
        permission=permission,
        resolved_evidence=frozenset({"evidence/EV-1"}),
        resolved_benchmarks=frozenset({"benchmark/M1.0"}),
    )
    transition = validate_transition(LifecycleState.CANDIDATE, LifecycleState.PROMOTED)
    passed = (
        decision.error_code is ErrorCode.PROMOTION_DENIED
        and transition.error_code is ErrorCode.ILLEGAL_TRANSITION
    )
    return _result(
        5,
        "Candidate direct promotion denial",
        passed,
        decision.error_code.value if decision.error_code else decision.decision.value,
        ErrorCode.PROMOTION_DENIED.value,
        error_code=decision.error_code,
    )


def _verified_promotion_allowed() -> ScenarioResult:
    _, owner, revision, acl = _fixture()
    store = _store(acl)
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="proof-create",
    )
    verify_event = StateEvent.create(
        memory_id=revision.memory_id,
        revision_id=revision.revision_id,
        from_state=LifecycleState.CANDIDATE,
        to_state=LifecycleState.VERIFIED,
        reason_code="VERIFIED",
        actor_principal_ref=owner.principal_id,
        policy_decision_ref="policy/verify",
        occurred_at=FIXED_NOW,
        nonce="proof-verify",
    )
    store.append_state_event(actor=owner, event=verify_event, correlation_id="proof-verify")
    promoted = store.promote(
        actor=owner,
        request=_promotion_request(owner, revision),
        correlation_id="proof-promote",
    )
    visible, _ = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(revision.namespace,),
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        now=FIXED_NOW + timedelta(seconds=2),
    )
    passed = promoted.effective_state is LifecycleState.PROMOTED and len(visible) == 1
    return _result(6, "Verified scoped promotion", passed, str(passed), "True")


def _stale_cas_conflict() -> ScenarioResult:
    _, owner, revision, acl = _fixture()
    store = _store(acl)
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    second = _next_revision(revision, "second", "idem-second", 2)
    store.compare_and_append_revision(
        actor=owner,
        revision=second,
        expected_head_revision_id=revision.revision_id,
        correlation_id="second",
    )
    stale = _next_revision(revision, "stale", "idem-stale", 2)
    outcome = store.compare_and_append_revision(
        actor=owner,
        revision=stale,
        expected_head_revision_id=revision.revision_id,
        correlation_id="stale",
    )
    head = store.get_head_revision(actor=owner, memory_id=revision.memory_id)
    passed = outcome.decision is Decision.CONFLICT and head.revision_id == second.revision_id
    return _result(
        7,
        "Stale CAS conflict",
        passed,
        outcome.error_code.value if outcome.error_code else outcome.decision.value,
        ErrorCode.REVISION_CONFLICT.value,
        error_code=outcome.error_code,
    )


def _idempotency_payload_mismatch() -> ScenarioResult:
    _, owner, revision, acl = _fixture()
    store = _store(acl)
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    changed = revision.model_copy(update={"content": {"candidate": "changed"}})
    observed = "NO_ERROR"
    code: ErrorCode | None = None
    try:
        store.append_revision(
            actor=owner,
            revision=changed,
            expected_head_revision_id=None,
            correlation_id="changed",
        )
    except MemoryContractError as exc:
        code = exc.code
        observed = exc.code.value
    passed = code is ErrorCode.DUPLICATE_IDEMPOTENCY_KEY
    return _result(
        8,
        "Idempotency payload mismatch rejection",
        passed,
        observed,
        ErrorCode.DUPLICATE_IDEMPOTENCY_KEY.value,
        error_code=code,
    )


def _forgotten_content_unavailable() -> ScenarioResult:
    _, owner, revision, acl = _fixture()
    store = _store(acl)
    store.append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=None,
        correlation_id="create",
    )
    store.revoke_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="REVOKE",
        policy_decision_ref="policy/revoke",
        correlation_id="revoke",
    )
    tombstone = store.forget_memory(
        actor=owner,
        memory_id=revision.memory_id,
        reason_code="FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="forget",
    )
    observed = "CONTENT_AVAILABLE"
    code: ErrorCode | None = None
    try:
        store.get_head_revision(actor=owner, memory_id=revision.memory_id)
    except MemoryContractError as exc:
        code = exc.code
        observed = exc.code.value
    passed = (
        code is ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE
        and store.verify_cache_and_index_invalidation(memory_id=revision.memory_id)
        and tombstone.prior_revision_hash == revision.content_hash
    )
    return _result(
        9,
        "Forgotten content unavailable",
        passed,
        observed,
        ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE.value,
        error_code=code,
    )


def _embedded_code_rejected() -> ScenarioResult:
    namespace, owner, revision, _ = _fixture()
    observed = "ACCEPTED"
    try:
        MemoryRevision.create(
            memory_id="mem_22222222222222222222222222222222",
            revision_nonce="skill-code",
            memory_kind=MemoryKind.SKILL,
            namespace=namespace,
            content={"capability_ref": "browser-check", "shell": "rm -rf /"},
            provenance=revision.provenance.model_copy(
                update={"transformation_kind": TransformationKind.SKILL_REGISTRATION}
            ),
            compatibility={
                "project_architecture_families": ("python-web",),
                "code_version_range": "1.x",
                "schema_version_range": "1.x",
                "capability_version_range": "1.x",
                "required_permissions": ("browser.read",),
                "executable_ref": "capability://browser-check@1.0.0",
            },
            retention_policy=RetentionPolicy(policy_ref="retention/skill"),
            formation_event_ref="formation/skill",
            created_by=owner.principal_id,
            idempotency_key="idem-skill-code",
            created_at=FIXED_NOW,
        )
    except ValidationError:
        observed = ErrorCode.INVALID_SCHEMA.value
    passed = observed == ErrorCode.INVALID_SCHEMA.value
    return _result(10, "Embedded executable rejection", passed, observed, "INVALID_SCHEMA")



def _deep_immutability_enforced() -> ScenarioResult:
    _, _, revision, _ = _fixture()
    observed = "MUTATION_ACCEPTED"
    try:
        revision.content["candidate"] = "tampered"
    except TypeError:
        observed = "IMMUTABLE"
    passed = observed == "IMMUTABLE" and revision.content_hash == canonical_sha256(
        revision.hash_payload()
    )
    return _result(
        11,
        "Governed revision deep immutability",
        passed,
        observed,
        "IMMUTABLE",
    )


def _campaign_scope_denied() -> ScenarioResult:
    _, owner, _, _ = _fixture()
    namespace = MemoryNamespace(
        organization_id="org-1",
        project_id="project-1",
        scope_kind=NamespaceScopeKind.CAMPAIGN,
        scope_id="campaign-red",
    )
    wrong_campaign = owner.model_copy(update={"campaign_id": "campaign-blue"})
    decision = evaluate_permission(
        actor=wrong_campaign,
        namespace=namespace,
        operation=AccessOperation.QUERY,
    )
    passed = decision.error_code is ErrorCode.NAMESPACE_DENIED
    return _result(
        12,
        "Exact campaign namespace isolation",
        passed,
        decision.error_code.value if decision.error_code else decision.decision.value,
        ErrorCode.NAMESPACE_DENIED.value,
        error_code=decision.error_code,
    )


def _expired_delegation_denied() -> ScenarioResult:
    namespace, owner, _, _ = _fixture()
    delegated = owner.model_copy(
        update={
            "delegator_ref": "user/owner",
            "delegation_scope": (namespace.canonical,),
            "delegation_expires_at": FIXED_NOW - timedelta(seconds=1),
            "audit_event_ref": "audit/delegation-proof",
        }
    )
    decision = evaluate_permission(
        actor=delegated,
        namespace=namespace,
        operation=AccessOperation.QUERY,
        now=FIXED_NOW,
    )
    passed = decision.error_code is ErrorCode.NAMESPACE_DENIED
    return _result(
        13,
        "Expired delegation denial",
        passed,
        decision.error_code.value if decision.error_code else decision.decision.value,
        ErrorCode.NAMESPACE_DENIED.value,
        error_code=decision.error_code,
    )


def _version_incompatibility_filtered() -> ScenarioResult:
    namespace, owner, revision, _ = _fixture()
    compatibility = CompatibilityDescriptor(
        project_architecture_families=("python-web",),
        code_version_range=">=1,<2",
        schema_version_range="1.x",
        capability_version_range="1.2.x",
        required_permissions=("browser.read",),
        executable_ref="capability://browser-check@1.2.0",
    )
    skill = MemoryRevision.create(
        memory_id="mem_33333333333333333333333333333333",
        revision_nonce="proof-skill-version",
        memory_kind=MemoryKind.SKILL,
        namespace=namespace,
        content={"capability_ref": "browser-check"},
        provenance=revision.provenance.model_copy(
            update={"transformation_kind": TransformationKind.SKILL_REGISTRATION}
        ),
        compatibility=compatibility,
        retention_policy=RetentionPolicy(policy_ref="retention/skill"),
        formation_event_ref="formation/proof-skill",
        created_by=owner.principal_id,
        idempotency_key="idem-proof-skill",
        created_at=FIXED_NOW,
    )
    decision = evaluate_effective_read(
        revision=skill,
        state=LifecycleState.PROMOTED,
        read_mode=ReadMode.PRODUCTION_RETRIEVAL,
        compatibility_context=CompatibilityContext(
            project_architecture_family="python-web",
            code_version="2.0.0",
            schema_version="1.0.0",
            capability_version="1.2.4",
            model_profile="deterministic",
            environment="test",
            permissions=("browser.read",),
        ),
        now=FIXED_NOW,
    )
    passed = decision.error_code is ErrorCode.COMPATIBILITY_FAILED
    return _result(
        14,
        "Compatibility version filtering",
        passed,
        decision.error_code.value if decision.error_code else decision.decision.value,
        ErrorCode.COMPATIBILITY_FAILED.value,
        error_code=decision.error_code,
    )


def _promoter_spoof_denied() -> ScenarioResult:
    namespace, owner, revision, _ = _fixture()
    permission = evaluate_permission(
        actor=owner, namespace=namespace, operation=AccessOperation.PROMOTE
    )
    request = _promotion_request(owner, revision).model_copy(
        update={"promoter_principal_ref": "agent-spoof"}
    )
    decision = validate_promotion(
        actor=owner,
        revision=revision,
        state=LifecycleState.VERIFIED,
        request=request,
        permission=permission,
        resolved_evidence=frozenset({"evidence/EV-1"}),
        resolved_benchmarks=frozenset({"benchmark/M1.0"}),
    )
    passed = decision.error_code is ErrorCode.PROMOTION_DENIED
    return _result(
        15,
        "Promoter identity spoof rejection",
        passed,
        decision.error_code.value if decision.error_code else decision.decision.value,
        ErrorCode.PROMOTION_DENIED.value,
        error_code=decision.error_code,
    )

def _fixture():
    namespace = MemoryNamespace(
        organization_id="org-1",
        project_id="project-1",
        scope_kind=NamespaceScopeKind.PROJECT,
        scope_id="project-1",
    )
    owner = PrincipalContext(
        principal_id="agent-owner",
        principal_type=PrincipalType.AGENT,
        organization_id="org-1",
        project_id="project-1",
        agent_id="agent-owner",
        role_ids=("OWNER", "VERIFIER", "PROMOTER", "PRIVACY_CONTROLLER"),
    )
    source_hash = canonical_sha256({"source": "approved requirement"})
    provenance = Provenance(
        source_refs=("requirement/REQ-1@3",),
        evidence_refs=("evidence/EV-1",),
        source_content_hashes={"requirement/REQ-1@3": source_hash},
        created_by_principal=owner.principal_id,
        creator_type=CreatorType.AGENT,
        capability_or_formation_rule_ref="formation/m1a-explicit",
        requirement_revision_refs=("requirement/REQ-1@3",),
        code_revision_refs=("code/proof",),
        environment_revision_refs=("env/proof",),
        model_or_provider_profile_refs=("model/deterministic",),
        transformation_kind=TransformationKind.EXTRACTION,
    )
    revision = MemoryRevision.create(
        memory_id="mem_11111111111111111111111111111111",
        revision_nonce="proof-revision-1",
        memory_kind=MemoryKind.SEMANTIC,
        namespace=namespace,
        content={"candidate": "timeout=30"},
        provenance=provenance,
        retention_policy=RetentionPolicy(policy_ref="retention/semantic"),
        formation_event_ref="formation/proof-1",
        created_by=owner.principal_id,
        idempotency_key="idem-proof-1",
        created_at=FIXED_NOW,
    )
    acl = (
        AclEntry(
            rule_id="bootstrap-manage-acl",
            effect=AclEffect.ALLOW,
            subject_type=AclSubjectType.PRINCIPAL,
            subject_id=owner.principal_id,
            operations=(AccessOperation.MANAGE_ACL,),
            namespace=namespace,
        ),
    )
    return namespace, owner, revision, acl


def _store(acl: tuple[AclEntry, ...]) -> DeterministicMemoryReference:
    return DeterministicMemoryReference(
        resolved_sources={
            "requirement/REQ-1@3": canonical_sha256({"source": "approved requirement"})
        },
        resolved_evidence=("evidence/EV-1",),
        resolved_benchmarks=("benchmark/M1.0",),
        initial_acl=acl,
    )


def _promotion_request(owner: PrincipalContext, revision: MemoryRevision) -> PromotionRequest:
    return PromotionRequest(
        memory_id=revision.memory_id,
        revision_id=revision.revision_id,
        declared_promotion_scope=revision.namespace,
        evidence_refs=("evidence/EV-1",),
        benchmark_or_evaluator_refs=("benchmark/M1.0",),
        promoter_principal_ref=owner.principal_id,
        policy_decision_ref="policy/promote",
        compatibility=None,
        effective_from=FIXED_NOW + timedelta(seconds=1),
        rollback_or_disable_ref="rollback/promotion-proof",
    )


def _next_revision(
    parent: MemoryRevision, value: str, idempotency_key: str, revision_number: int
) -> MemoryRevision:
    return MemoryRevision.create(
        memory_id=parent.memory_id,
        revision_nonce=value,
        revision_number=revision_number,
        parent_revision_refs=(parent.ref,),
        memory_kind=parent.memory_kind,
        namespace=parent.namespace,
        content={"candidate": value},
        provenance=parent.provenance,
        retention_policy=parent.retention_policy,
        formation_event_ref=f"formation/{value}",
        created_by=parent.created_by,
        idempotency_key=idempotency_key,
        created_at=FIXED_NOW + timedelta(minutes=revision_number),
    )


def _result(
    index: int,
    title: str,
    passed: bool,
    observed: str,
    expected: str,
    *,
    error_code: ErrorCode | None = None,
    **evidence: Any,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=f"M1A-RC-{index:03d}",
        title=title,
        passed=passed,
        observed=observed,
        expected=expected,
        error_code=error_code.value if error_code else None,
        evidence=evidence,
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_markdown(report: ContractProofReport) -> str:
    lines = [
        "# M1A Runtime Contract Proof",
        "",
        f"- Verdict: `{report.verdict}`",
        f"- Scenarios: `{report.metrics.passed}/{report.metrics.total}`",
        f"- Critical False Green: `{report.metrics.critical_false_green}`",
        f"- Semantic Digest: `{report.semantic_digest}`",
        "",
        "| Scenario | Result | Observed |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| {result.scenario_id} {result.title} | {'PASS' if result.passed else 'FAIL'} | "
        f"{result.observed} |"
        for result in report.results
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="M1A governed Memory contract proof")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", type=Path, required=True)
    run_parser.add_argument("--code-sha", default="local")
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        report = run_contract_proof(args.output_dir, code_sha=args.code_sha)
        return 0 if report.verdict == "PASS" else 1
    result = replay_contract_proof(args.output_dir)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
