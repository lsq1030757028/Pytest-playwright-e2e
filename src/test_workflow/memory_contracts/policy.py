from __future__ import annotations

from datetime import UTC, datetime

from .models import (
    AccessOperation,
    AclEffect,
    AclEntry,
    AclSubjectType,
    CompatibilityContext,
    CompatibilityDescriptor,
    Decision,
    EffectiveReadDecision,
    ErrorCode,
    LifecycleState,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    NamespaceScopeKind,
    PermissionDecision,
    PrincipalContext,
    PromotionDecision,
    PromotionRequest,
    ReadMode,
    TransitionDecision,
)

ROLE_PERMISSIONS: dict[str, frozenset[AccessOperation]] = {
    "OWNER": frozenset(
        {
            AccessOperation.READ_METADATA,
            AccessOperation.READ_CONTENT,
            AccessOperation.QUERY,
            AccessOperation.APPEND_REVISION,
            AccessOperation.APPEND_STATE_EVENT,
            AccessOperation.AUDIT,
        }
    ),
    "READER": frozenset(
        {
            AccessOperation.READ_METADATA,
            AccessOperation.READ_CONTENT,
            AccessOperation.QUERY,
        }
    ),
    "WRITER": frozenset(
        {
            AccessOperation.READ_METADATA,
            AccessOperation.READ_CONTENT,
            AccessOperation.QUERY,
            AccessOperation.APPEND_REVISION,
            AccessOperation.APPEND_STATE_EVENT,
        }
    ),
    "VERIFIER": frozenset(
        {
            AccessOperation.READ_METADATA,
            AccessOperation.READ_CONTENT,
            AccessOperation.QUERY,
            AccessOperation.VERIFY,
            AccessOperation.AUDIT,
        }
    ),
    "PROMOTER": frozenset(
        {
            AccessOperation.READ_METADATA,
            AccessOperation.READ_CONTENT,
            AccessOperation.QUERY,
            AccessOperation.PROMOTE,
            AccessOperation.SUPERSEDE,
            AccessOperation.REVOKE,
            AccessOperation.AUDIT,
        }
    ),
    "PRIVACY_CONTROLLER": frozenset(
        {
            AccessOperation.READ_METADATA,
            AccessOperation.REVOKE,
            AccessOperation.FORGET,
            AccessOperation.AUDIT,
        }
    ),
    "AUDITOR": frozenset({AccessOperation.READ_METADATA, AccessOperation.AUDIT}),
}

ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.CANDIDATE: frozenset(
        {
            LifecycleState.VERIFIED,
            LifecycleState.CONFLICTING,
            LifecycleState.QUARANTINED,
            LifecycleState.REVOKED,
            LifecycleState.EXPIRED,
        }
    ),
    LifecycleState.VERIFIED: frozenset(
        {
            LifecycleState.PROMOTED,
            LifecycleState.CONFLICTING,
            LifecycleState.QUARANTINED,
            LifecycleState.SUPERSEDED,
            LifecycleState.REVOKED,
            LifecycleState.EXPIRED,
        }
    ),
    LifecycleState.PROMOTED: frozenset(
        {
            LifecycleState.CONFLICTING,
            LifecycleState.QUARANTINED,
            LifecycleState.SUPERSEDED,
            LifecycleState.REVOKED,
            LifecycleState.EXPIRED,
        }
    ),
    LifecycleState.CONFLICTING: frozenset(
        {
            LifecycleState.VERIFIED,
            LifecycleState.QUARANTINED,
            LifecycleState.SUPERSEDED,
            LifecycleState.REVOKED,
        }
    ),
    LifecycleState.QUARANTINED: frozenset(
        {
            LifecycleState.CANDIDATE,
            LifecycleState.REVOKED,
            LifecycleState.FORGOTTEN,
        }
    ),
    LifecycleState.SUPERSEDED: frozenset({LifecycleState.FORGOTTEN}),
    LifecycleState.REVOKED: frozenset({LifecycleState.FORGOTTEN}),
    LifecycleState.EXPIRED: frozenset(
        {LifecycleState.CANDIDATE, LifecycleState.FORGOTTEN}
    ),
    LifecycleState.FORGOTTEN: frozenset(),
}

READ_STATES: dict[ReadMode, frozenset[LifecycleState]] = {
    ReadMode.ADVISORY: frozenset({LifecycleState.CANDIDATE}),
    ReadMode.EVIDENCE_BEARING: frozenset({LifecycleState.VERIFIED}),
    ReadMode.PRODUCTION_RETRIEVAL: frozenset({LifecycleState.PROMOTED}),
}

PROMOTABLE_KINDS = frozenset(
    {MemoryKind.SEMANTIC, MemoryKind.PROCEDURAL, MemoryKind.SKILL}
)


def namespace_authorized(actor: PrincipalContext, namespace: MemoryNamespace) -> bool:
    if actor.organization_id != namespace.organization_id:
        return False
    if namespace.scope_kind is NamespaceScopeKind.ORGANIZATION:
        return actor.organization_id == namespace.scope_id
    if namespace.scope_kind is NamespaceScopeKind.SHARED:
        return namespace.scope_id in actor.shared_scope_ids
    if actor.project_id != namespace.project_id:
        return False
    if namespace.scope_kind is NamespaceScopeKind.AGENT:
        return actor.agent_id == namespace.scope_id
    return True


def evaluate_permission(
    *,
    actor: PrincipalContext,
    namespace: MemoryNamespace,
    operation: AccessOperation,
    acl_entries: tuple[AclEntry, ...] = (),
    namespace_policy_denies: tuple[AccessOperation, ...] = (),
    relevance_score: float | None = None,
) -> PermissionDecision:
    del relevance_score
    if not namespace_authorized(actor, namespace):
        return PermissionDecision(
            decision=Decision.DENY,
            operation=operation,
            namespace=namespace.canonical,
            error_code=ErrorCode.NAMESPACE_DENIED,
            reason="actor is outside the exact authorized namespace",
        )

    matching = tuple(
        entry
        for entry in acl_entries
        if entry.namespace == namespace
        and operation in entry.operations
        and _subject_matches(actor, entry)
    )
    denied = tuple(entry.rule_id for entry in matching if entry.effect is AclEffect.DENY)
    if denied:
        return PermissionDecision(
            decision=Decision.DENY,
            operation=operation,
            namespace=namespace.canonical,
            matched_rule_ids=denied,
            error_code=ErrorCode.ACL_DENIED,
            reason="explicit DENY overrides all ALLOW paths",
        )
    if operation in namespace_policy_denies:
        return PermissionDecision(
            decision=Decision.DENY,
            operation=operation,
            namespace=namespace.canonical,
            error_code=ErrorCode.ACL_DENIED,
            reason="namespace policy denied the operation",
        )
    allowed = tuple(entry.rule_id for entry in matching if entry.effect is AclEffect.ALLOW)
    if allowed:
        return PermissionDecision(
            decision=Decision.ALLOW,
            operation=operation,
            namespace=namespace.canonical,
            matched_rule_ids=allowed,
            reason="explicit ACL ALLOW",
        )
    allowed_roles = tuple(
        role for role in actor.role_ids if operation in ROLE_PERMISSIONS.get(role, frozenset())
    )
    if allowed_roles:
        return PermissionDecision(
            decision=Decision.ALLOW,
            operation=operation,
            namespace=namespace.canonical,
            matched_rule_ids=tuple(f"role:{role}" for role in allowed_roles),
            reason="namespace role permits the operation",
        )
    return PermissionDecision(
        decision=Decision.DENY,
        operation=operation,
        namespace=namespace.canonical,
        error_code=ErrorCode.ACL_DENIED,
        reason="default deny",
    )


def validate_transition(
    from_state: LifecycleState, to_state: LifecycleState
) -> TransitionDecision:
    if to_state in ALLOWED_TRANSITIONS[from_state]:
        return TransitionDecision(
            decision=Decision.ACCEPTED,
            from_state=from_state,
            to_state=to_state,
            reason="transition is allowed by the approved lifecycle graph",
        )
    return TransitionDecision(
        decision=Decision.REJECTED,
        from_state=from_state,
        to_state=to_state,
        error_code=ErrorCode.ILLEGAL_TRANSITION,
        reason="transition is not allowed by the approved lifecycle graph",
    )


def validate_promotion(
    *,
    revision: MemoryRevision,
    state: LifecycleState,
    request: PromotionRequest,
    permission: PermissionDecision,
) -> PromotionDecision:
    if revision.memory_kind not in PROMOTABLE_KINDS:
        return PromotionDecision(
            decision=Decision.REJECTED,
            error_code=ErrorCode.PROMOTION_DENIED,
            reason=f"{revision.memory_kind.value} memory is not promotable",
        )
    if state is not LifecycleState.VERIFIED:
        return PromotionDecision(
            decision=Decision.REJECTED,
            error_code=ErrorCode.PROMOTION_DENIED,
            reason="promotion requires VERIFIED state",
        )
    if not permission.allowed or permission.operation is not AccessOperation.PROMOTE:
        return PromotionDecision(
            decision=Decision.REJECTED,
            error_code=ErrorCode.PROMOTION_DENIED,
            reason="promoter lacks PROMOTE permission",
        )
    if request.memory_id != revision.memory_id or request.revision_id != revision.revision_id:
        return PromotionDecision(
            decision=Decision.REJECTED,
            error_code=ErrorCode.PROMOTION_DENIED,
            reason="promotion request does not identify the effective revision",
        )
    if request.declared_promotion_scope != revision.namespace:
        return PromotionDecision(
            decision=Decision.REJECTED,
            error_code=ErrorCode.PROMOTION_DENIED,
            reason="scope expansion requires a separately authorized promotion event",
        )
    if revision.memory_kind in {MemoryKind.PROCEDURAL, MemoryKind.SKILL}:
        if request.compatibility != revision.compatibility:
            return PromotionDecision(
                decision=Decision.REJECTED,
                error_code=ErrorCode.COMPATIBILITY_FAILED,
                reason="promotion compatibility must match the governed revision",
            )
    return PromotionDecision(
        decision=Decision.ACCEPTED,
        reason=(
            "revision is admitted only to the declared retrieval scope; protected authority "
            "is unchanged"
        ),
    )


def evaluate_effective_read(
    *,
    revision: MemoryRevision,
    state: LifecycleState,
    read_mode: ReadMode,
    now: datetime | None = None,
    compatibility_context: CompatibilityContext | None = None,
) -> EffectiveReadDecision:
    resolved_now = now or datetime.now(UTC)
    expiry = revision.retention_policy.effective_expiry(revision.created_at)
    if expiry is not None and resolved_now >= expiry:
        return EffectiveReadDecision(
            decision=Decision.FILTERED,
            state=LifecycleState.EXPIRED,
            read_mode=read_mode,
            error_code=ErrorCode.MEMORY_NOT_EFFECTIVE,
            reason="retention expired before retrieval",
        )
    if state is LifecycleState.FORGOTTEN:
        return EffectiveReadDecision(
            decision=Decision.FILTERED,
            state=state,
            read_mode=read_mode,
            error_code=ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE,
            reason="forgotten content is unavailable",
        )
    if state not in READ_STATES[read_mode]:
        return EffectiveReadDecision(
            decision=Decision.FILTERED,
            state=state,
            read_mode=read_mode,
            error_code=ErrorCode.MEMORY_NOT_EFFECTIVE,
            reason=f"{state.value} is not effective for {read_mode.value}",
        )
    if revision.memory_kind in {MemoryKind.PROCEDURAL, MemoryKind.SKILL}:
        if compatibility_context is None or revision.compatibility is None:
            return EffectiveReadDecision(
                decision=Decision.FILTERED,
                state=state,
                read_mode=read_mode,
                error_code=ErrorCode.COMPATIBILITY_FAILED,
                reason="procedural and skill memory require compatibility context",
            )
        if not compatibility_matches(revision.compatibility, compatibility_context):
            return EffectiveReadDecision(
                decision=Decision.FILTERED,
                state=state,
                read_mode=read_mode,
                error_code=ErrorCode.COMPATIBILITY_FAILED,
                reason="memory is incompatible with the current execution context",
            )
    return EffectiveReadDecision(
        decision=Decision.ALLOW,
        state=state,
        read_mode=read_mode,
        reason="memory is effective for the requested read mode",
    )


def compatibility_matches(
    descriptor: CompatibilityDescriptor, context: CompatibilityContext
) -> bool:
    architectures = set(descriptor.project_architecture_families)
    if "*" not in architectures and context.project_architecture_family not in architectures:
        return False
    if (
        descriptor.model_profile_constraints
        and context.model_profile not in descriptor.model_profile_constraints
    ):
        return False
    if (
        descriptor.environment_constraints
        and context.environment not in descriptor.environment_constraints
    ):
        return False
    if not set(descriptor.required_permissions) <= set(context.permissions):
        return False
    if set(descriptor.incompatible_conditions) & set(context.active_conditions):
        return False
    return True


def operation_for_transition(target: LifecycleState) -> AccessOperation:
    mapping = {
        LifecycleState.VERIFIED: AccessOperation.VERIFY,
        LifecycleState.PROMOTED: AccessOperation.PROMOTE,
        LifecycleState.SUPERSEDED: AccessOperation.SUPERSEDE,
        LifecycleState.REVOKED: AccessOperation.REVOKE,
        LifecycleState.FORGOTTEN: AccessOperation.FORGET,
    }
    return mapping.get(target, AccessOperation.APPEND_STATE_EVENT)


def _subject_matches(actor: PrincipalContext, entry: AclEntry) -> bool:
    if entry.subject_type is AclSubjectType.PRINCIPAL:
        return entry.subject_id == actor.principal_id
    if entry.subject_type is AclSubjectType.GROUP:
        return entry.subject_id in actor.group_ids
    return entry.subject_id in actor.role_ids
