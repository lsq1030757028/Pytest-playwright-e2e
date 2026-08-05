from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable
from uuid import uuid4

from pydantic import ValidationError

from .canonical import canonical_sha256
from .models import (
    AccessOperation,
    AclEntry,
    AppendRevisionResult,
    AuditEvent,
    ConflictArtifact,
    Decision,
    ErrorCode,
    ForgetTombstone,
    LifecycleState,
    MemoryContractError,
    MemoryNamespace,
    MemoryRevision,
    MutationResult,
    PrincipalContext,
    PromotionRequest,
    ReadMode,
    StateEvent,
)
from .policy import (
    evaluate_effective_read,
    evaluate_permission,
    operation_for_transition,
    validate_promotion,
    validate_transition,
)


class DeterministicMemoryReference:
    """In-memory reference adapter proving M1A contracts, not a production store."""

    def __init__(
        self,
        *,
        resolved_sources: dict[str, str] | None = None,
        resolved_evidence: Iterable[str] = (),
        resolved_benchmarks: Iterable[str] = (),
        initial_acl: Iterable[AclEntry] = (),
    ) -> None:
        self._revisions: dict[str, list[MemoryRevision]] = {}
        self._states: dict[str, list[StateEvent]] = {}
        self._acl: dict[str, list[AclEntry]] = {}
        self._audits: list[AuditEvent] = []
        self._idempotency: dict[str, tuple[str, AppendRevisionResult]] = {}
        self._tombstones: dict[str, ForgetTombstone] = {}
        self._invalidated: set[str] = set()
        self._resolved_sources = dict(resolved_sources or {})
        self._resolved_evidence = set(resolved_evidence)
        self._resolved_benchmarks = set(resolved_benchmarks)
        for entry in initial_acl:
            self._acl.setdefault(entry.namespace.canonical, []).append(entry)

    def append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str | None,
        correlation_id: str,
    ) -> AppendRevisionResult:
        fingerprint = canonical_sha256(revision.model_dump(mode="json"))
        existing = self._idempotency.get(revision.idempotency_key)
        if existing is not None:
            existing_fingerprint, result = existing
            if existing_fingerprint != fingerprint:
                raise MemoryContractError(
                    ErrorCode.DUPLICATE_IDEMPOTENCY_KEY,
                    "idempotency key was reused with a different payload",
                )
            return result.model_copy(update={"decision": Decision.IDEMPOTENT_REPLAY})
        try:
            revision = MemoryRevision.model_validate(revision.model_dump(mode="python"))
        except ValidationError:
            return AppendRevisionResult(
                decision=Decision.REJECTED,
                error_code=ErrorCode.INVALID_SCHEMA,
            )
        permission = self.evaluate_permission(
            actor=actor,
            namespace=revision.namespace,
            operation=AccessOperation.APPEND_REVISION,
        )
        if not permission.allowed:
            return AppendRevisionResult(
                decision=Decision.REJECTED,
                error_code=permission.error_code,
            )
        provenance_error = self._validate_provenance(revision)
        if provenance_error is not None:
            result = AppendRevisionResult(
                decision=Decision.REJECTED,
                error_code=ErrorCode.PROVENANCE_MISSING,
            )
            self._idempotency[revision.idempotency_key] = (fingerprint, result)
            return result

        history = self._revisions.get(revision.memory_id, [])
        current = history[-1] if history else None
        if current is None:
            if expected_head_revision_id is not None or revision.revision_number != 1:
                result = self._conflict_result(
                    actor=actor,
                    revision=revision,
                    base_revision_id=expected_head_revision_id,
                    current_head_revision_id=None,
                    conflicting_fields=("expected_head_revision_id", "revision_number"),
                )
                self._idempotency[revision.idempotency_key] = (fingerprint, result)
                return result
        else:
            conflicts: list[str] = []
            if expected_head_revision_id != current.revision_id:
                conflicts.append("expected_head_revision_id")
            if revision.revision_number != current.revision_number + 1:
                conflicts.append("revision_number")
            if current.ref not in revision.parent_revision_refs:
                conflicts.append("parent_revision_refs")
            if revision.namespace != current.namespace:
                old_permission = self.evaluate_permission(
                    actor=actor,
                    namespace=current.namespace,
                    operation=AccessOperation.APPEND_REVISION,
                )
                if not old_permission.allowed:
                    conflicts.append("namespace_authority")
            if conflicts:
                result = self._conflict_result(
                    actor=actor,
                    revision=revision,
                    base_revision_id=expected_head_revision_id,
                    current_head_revision_id=current.revision_id,
                    conflicting_fields=tuple(conflicts),
                )
                self._idempotency[revision.idempotency_key] = (fingerprint, result)
                return result

        self._revisions.setdefault(revision.memory_id, []).append(revision)
        audit_ref = self._record_audit(
            event_type="MEMORY_CREATED" if current is None else "REVISION_APPENDED",
            revision=revision,
            actor=actor,
            reason_code="CONTRACT_ACCEPTED",
            policy_decision_ref="policy/m1a/append",
            occurred_at=revision.created_at,
            correlation_id=correlation_id,
        )
        result = AppendRevisionResult(
            decision=Decision.ACCEPTED,
            effective_revision_ref=revision.ref,
            effective_state=self.get_effective_state(memory_id=revision.memory_id),
            audit_event_ref=audit_ref,
            revision=revision,
        )
        self._idempotency[revision.idempotency_key] = (fingerprint, result)
        return result

    def compare_and_append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str,
        correlation_id: str,
    ) -> AppendRevisionResult:
        return self.append_revision(
            actor=actor,
            revision=revision,
            expected_head_revision_id=expected_head_revision_id,
            correlation_id=correlation_id,
        )

    def get_revision(
        self, *, actor: PrincipalContext, memory_id: str, revision_id: str
    ) -> MemoryRevision:
        self._assert_not_forgotten(memory_id)
        revision = next(
            (
                item
                for item in self._revisions.get(memory_id, [])
                if item.revision_id == revision_id
            ),
            None,
        )
        if revision is None:
            raise MemoryContractError(ErrorCode.MEMORY_NOT_FOUND, "revision not found")
        self._require_permission(actor, revision.namespace, AccessOperation.READ_CONTENT)
        return revision

    def get_head_revision(
        self, *, actor: PrincipalContext, memory_id: str
    ) -> MemoryRevision:
        self._assert_not_forgotten(memory_id)
        history = self._revisions.get(memory_id, [])
        if not history:
            raise MemoryContractError(ErrorCode.MEMORY_NOT_FOUND, "memory not found")
        revision = history[-1]
        self._require_permission(actor, revision.namespace, AccessOperation.READ_CONTENT)
        return revision

    def list_revision_history(
        self, *, actor: PrincipalContext, memory_id: str
    ) -> tuple[MemoryRevision, ...]:
        self._assert_not_forgotten(memory_id)
        history = tuple(self._revisions.get(memory_id, []))
        if not history:
            raise MemoryContractError(ErrorCode.MEMORY_NOT_FOUND, "memory not found")
        self._require_permission(actor, history[-1].namespace, AccessOperation.READ_METADATA)
        return history

    def append_state_event(
        self, *, actor: PrincipalContext, event: StateEvent, correlation_id: str
    ) -> MutationResult:
        try:
            event = StateEvent.model_validate(event.model_dump(mode="python"))
        except ValidationError:
            return MutationResult(
                decision=Decision.REJECTED,
                error_code=ErrorCode.INVALID_SCHEMA,
            )
        revision = self._head_without_permission(event.memory_id)
        if event.actor_principal_ref != actor.principal_id:
            return MutationResult(
                decision=Decision.REJECTED,
                error_code=ErrorCode.ACL_DENIED,
            )
        if revision.revision_id != event.revision_id:
            return MutationResult(
                decision=Decision.REJECTED,
                effective_revision_ref=revision.ref,
                effective_state=self.get_effective_state(memory_id=event.memory_id),
                error_code=ErrorCode.REVISION_CONFLICT,
            )
        current = self.get_effective_state(memory_id=event.memory_id)
        if event.from_state is not current:
            return MutationResult(
                decision=Decision.REJECTED,
                effective_revision_ref=revision.ref,
                effective_state=current,
                error_code=ErrorCode.REVISION_CONFLICT,
            )
        permission = self.evaluate_permission(
            actor=actor,
            namespace=revision.namespace,
            operation=operation_for_transition(event.to_state),
        )
        if not permission.allowed:
            return MutationResult(
                decision=Decision.REJECTED,
                effective_revision_ref=revision.ref,
                effective_state=current,
                error_code=permission.error_code,
            )
        transition = validate_transition(current, event.to_state)
        if transition.decision is not Decision.ACCEPTED:
            return MutationResult(
                decision=Decision.REJECTED,
                effective_revision_ref=revision.ref,
                effective_state=current,
                error_code=transition.error_code,
            )
        self._states.setdefault(event.memory_id, []).append(event)
        audit_ref = self._record_audit(
            event_type="STATE_TRANSITIONED",
            revision=revision,
            actor=actor,
            reason_code=event.reason_code,
            policy_decision_ref=event.policy_decision_ref,
            occurred_at=event.occurred_at,
            correlation_id=correlation_id,
        )
        return MutationResult(
            decision=Decision.ACCEPTED,
            effective_revision_ref=revision.ref,
            effective_state=event.to_state,
            audit_event_ref=audit_ref,
        )

    def promote(
        self,
        *,
        actor: PrincipalContext,
        request: PromotionRequest,
        correlation_id: str,
    ) -> MutationResult:
        revision = self._head_without_permission(request.memory_id)
        state = self.get_effective_state(memory_id=request.memory_id)
        permission = self.evaluate_permission(
            actor=actor,
            namespace=revision.namespace,
            operation=AccessOperation.PROMOTE,
        )
        decision = validate_promotion(
            actor=actor,
            revision=revision,
            state=state,
            request=request,
            permission=permission,
            resolved_evidence=frozenset(self._resolved_evidence),
            resolved_benchmarks=frozenset(self._resolved_benchmarks),
        )
        if decision.decision is not Decision.ACCEPTED:
            return MutationResult(
                decision=Decision.REJECTED,
                effective_revision_ref=revision.ref,
                effective_state=state,
                error_code=decision.error_code,
            )
        event = StateEvent.create(
            memory_id=revision.memory_id,
            revision_id=revision.revision_id,
            from_state=state,
            to_state=LifecycleState.PROMOTED,
            reason_code="PROMOTION_APPROVED",
            actor_principal_ref=actor.principal_id,
            policy_decision_ref=request.policy_decision_ref,
            occurred_at=request.effective_from,
        )
        return self.append_state_event(actor=actor, event=event, correlation_id=correlation_id)

    def get_effective_state(self, *, memory_id: str) -> LifecycleState:
        if memory_id in self._tombstones:
            return LifecycleState.FORGOTTEN
        events = self._states.get(memory_id, [])
        return events[-1].to_state if events else LifecycleState.CANDIDATE

    def list_state_history(self, *, memory_id: str) -> tuple[StateEvent, ...]:
        return tuple(self._states.get(memory_id, []))

    def evaluate_permission(
        self,
        *,
        actor: PrincipalContext,
        namespace: MemoryNamespace,
        operation: AccessOperation,
    ):
        return evaluate_permission(
            actor=actor,
            namespace=namespace,
            operation=operation,
            acl_entries=tuple(self._acl.get(namespace.canonical, [])),
        )

    def append_acl_event(
        self,
        *,
        actor: PrincipalContext,
        entry: AclEntry,
        correlation_id: str,
    ) -> MutationResult:
        permission = self.evaluate_permission(
            actor=actor,
            namespace=entry.namespace,
            operation=AccessOperation.MANAGE_ACL,
        )
        if not permission.allowed:
            return MutationResult(decision=Decision.REJECTED, error_code=permission.error_code)
        self._acl.setdefault(entry.namespace.canonical, []).append(entry)
        return MutationResult(
            decision=Decision.ACCEPTED,
            audit_event_ref=(
                "acl:"
                + canonical_sha256({"entry": entry, "correlation": correlation_id})
            ),
        )

    def list_effective_acl(self, *, namespace: MemoryNamespace) -> tuple[AclEntry, ...]:
        return tuple(self._acl.get(namespace.canonical, []))

    def query_exact_authorized_namespaces(
        self,
        *,
        actor: PrincipalContext,
        namespaces: tuple[MemoryNamespace, ...],
        read_mode: ReadMode,
        compatibility_context=None,
        now: datetime | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[tuple[MemoryRevision, ...], str | None]:
        allowed_namespace_strings = {
            namespace.canonical
            for namespace in namespaces
            if self.evaluate_permission(
                actor=actor,
                namespace=namespace,
                operation=AccessOperation.QUERY,
            ).allowed
        }
        selected: list[MemoryRevision] = []
        for memory_id, history in self._revisions.items():
            if memory_id in self._tombstones or not history:
                continue
            revision = history[-1]
            if revision.namespace.canonical not in allowed_namespace_strings:
                continue
            state = self.get_effective_state(memory_id=memory_id)
            effective = evaluate_effective_read(
                revision=revision,
                state=state,
                read_mode=read_mode,
                now=now,
                compatibility_context=compatibility_context,
            )
            if effective.decision is Decision.ALLOW:
                selected.append(revision)
        return self.paginate_deterministically(tuple(selected), cursor=cursor, limit=limit)

    def filter_by_metadata(
        self,
        revisions: tuple[MemoryRevision, ...],
        *,
        memory_kind: str | None = None,
        schema_version: str | None = None,
    ) -> tuple[MemoryRevision, ...]:
        return tuple(
            revision
            for revision in revisions
            if (memory_kind is None or revision.memory_kind.value == memory_kind)
            and (schema_version is None or revision.schema_version == schema_version)
        )

    def paginate_deterministically(
        self,
        revisions: tuple[MemoryRevision, ...],
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[tuple[MemoryRevision, ...], str | None]:
        if limit < 1:
            raise ValueError("limit must be positive")
        ordered = sorted(revisions, key=lambda item: (item.namespace.canonical, item.ref))
        start = 0
        if cursor is not None:
            for index, item in enumerate(ordered):
                if item.ref == cursor:
                    start = index + 1
                    break
            else:
                raise ValueError("invalid deterministic cursor")
        page = tuple(ordered[start : start + limit])
        next_cursor = page[-1].ref if start + limit < len(ordered) and page else None
        return page, next_cursor

    def append_audit_event(self, event: AuditEvent) -> str:
        expected_previous = self._audits[-1].event_hash if self._audits else None
        if event.previous_event_hash != expected_previous:
            raise MemoryContractError(ErrorCode.INTEGRITY_FAILED, "audit chain head mismatch")
        self._audits.append(event)
        return event.event_id

    def list_audit_events(self, *, memory_id: str | None = None) -> tuple[AuditEvent, ...]:
        if memory_id is None:
            return tuple(self._audits)
        return tuple(event for event in self._audits if event.memory_id == memory_id)

    def verify_event_chain(self) -> bool:
        previous: str | None = None
        for event in self._audits:
            if event.previous_event_hash != previous:
                return False
            if event.event_hash != canonical_sha256(event.hash_payload()):
                return False
            previous = event.event_hash
        return True

    def expire_due_memories(
        self, *, actor: PrincipalContext, now: datetime, correlation_id: str
    ) -> tuple[str, ...]:
        expired: list[str] = []
        for memory_id, history in tuple(self._revisions.items()):
            if memory_id in self._tombstones or not history:
                continue
            revision = history[-1]
            expiry = revision.retention_policy.effective_expiry(revision.created_at)
            state = self.get_effective_state(memory_id=memory_id)
            if expiry is None or now < expiry or state in {
                LifecycleState.EXPIRED,
                LifecycleState.FORGOTTEN,
            }:
                continue
            event = StateEvent.create(
                memory_id=memory_id,
                revision_id=revision.revision_id,
                from_state=state,
                to_state=LifecycleState.EXPIRED,
                reason_code="RETENTION_EXPIRED",
                actor_principal_ref=actor.principal_id,
                policy_decision_ref="policy/m1a/retention",
                occurred_at=now,
            )
            result = self.append_state_event(
                actor=actor, event=event, correlation_id=correlation_id
            )
            if result.decision is Decision.ACCEPTED:
                self._invalidated.add(memory_id)
                expired.append(memory_id)
        return tuple(expired)

    def revoke_memory(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        reason_code: str,
        policy_decision_ref: str,
        correlation_id: str,
    ) -> MutationResult:
        revision = self._head_without_permission(memory_id)
        state = self.get_effective_state(memory_id=memory_id)
        event = StateEvent.create(
            memory_id=memory_id,
            revision_id=revision.revision_id,
            from_state=state,
            to_state=LifecycleState.REVOKED,
            reason_code=reason_code,
            actor_principal_ref=actor.principal_id,
            policy_decision_ref=policy_decision_ref,
        )
        result = self.append_state_event(actor=actor, event=event, correlation_id=correlation_id)
        if result.decision is Decision.ACCEPTED:
            self._invalidated.add(memory_id)
        return result

    def forget_memory(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        reason_code: str,
        policy_decision_ref: str,
        correlation_id: str,
    ) -> ForgetTombstone:
        revision = self._head_without_permission(memory_id)
        current = self.get_effective_state(memory_id=memory_id)
        if current not in {
            LifecycleState.QUARANTINED,
            LifecycleState.SUPERSEDED,
            LifecycleState.REVOKED,
            LifecycleState.EXPIRED,
        }:
            raise MemoryContractError(
                ErrorCode.ILLEGAL_TRANSITION,
                "memory must be non-effective before forget",
            )
        permission = self.evaluate_permission(
            actor=actor,
            namespace=revision.namespace,
            operation=AccessOperation.FORGET,
        )
        if not permission.allowed:
            code = permission.error_code or ErrorCode.ACL_DENIED
            raise MemoryContractError(code, permission.reason)
        event = StateEvent.create(
            memory_id=memory_id,
            revision_id=revision.revision_id,
            from_state=current,
            to_state=LifecycleState.FORGOTTEN,
            reason_code=reason_code,
            actor_principal_ref=actor.principal_id,
            policy_decision_ref=policy_decision_ref,
        )
        transition = validate_transition(current, LifecycleState.FORGOTTEN)
        if transition.decision is not Decision.ACCEPTED:
            raise MemoryContractError(ErrorCode.ILLEGAL_TRANSITION, transition.reason)
        self._states.setdefault(memory_id, []).append(event)
        audit_ref = self._record_audit(
            event_type="FORGOTTEN",
            revision=revision,
            actor=actor,
            reason_code=reason_code,
            policy_decision_ref=policy_decision_ref,
            occurred_at=event.occurred_at,
            correlation_id=correlation_id,
        )
        tombstone = ForgetTombstone(
            memory_id=memory_id,
            namespace_hash=revision.namespace.namespace_hash,
            memory_kind=revision.memory_kind,
            forgotten_at=event.occurred_at,
            reason_code=reason_code,
            authority_event_ref=audit_ref,
            prior_revision_hash=revision.content_hash,
        )
        self._tombstones[memory_id] = tombstone
        self._revisions.pop(memory_id, None)
        self._invalidated.add(memory_id)
        return tombstone

    def verify_cache_and_index_invalidation(self, *, memory_id: str) -> bool:
        return memory_id in self._invalidated

    def get_tombstone(self, *, memory_id: str) -> ForgetTombstone | None:
        return self._tombstones.get(memory_id)

    def _validate_provenance(self, revision: MemoryRevision) -> ErrorCode | None:
        for source_ref, expected_hash in revision.provenance.source_content_hashes.items():
            if self._resolved_sources.get(source_ref) != expected_hash:
                return ErrorCode.PROVENANCE_MISSING
        if not set(revision.provenance.evidence_refs) <= self._resolved_evidence:
            return ErrorCode.PROVENANCE_MISSING
        return None

    def _conflict_result(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        base_revision_id: str | None,
        current_head_revision_id: str | None,
        conflicting_fields: tuple[str, ...],
    ) -> AppendRevisionResult:
        detected_at = datetime.now(UTC)
        seed = {
            "memory_id": revision.memory_id,
            "base": base_revision_id,
            "current": current_head_revision_id,
            "attempted": revision.revision_id,
            "fields": conflicting_fields,
            "detected_at": detected_at,
            "actor": actor.principal_id,
            "nonce": uuid4().hex,
        }
        conflict = ConflictArtifact(
            conflict_id=f"conflict_{canonical_sha256(seed)}",
            memory_id=revision.memory_id,
            base_revision_id=base_revision_id,
            current_head_revision_id=current_head_revision_id,
            attempted_revision_id=revision.revision_id,
            conflicting_fields=conflicting_fields,
            detected_at=detected_at,
            actor_ref=actor.principal_id,
        )
        return AppendRevisionResult(
            decision=Decision.CONFLICT,
            effective_revision_ref=(
                f"{revision.memory_id}@{current_head_revision_id}"
                if current_head_revision_id
                else None
            ),
            effective_state=(
                self.get_effective_state(memory_id=revision.memory_id)
                if current_head_revision_id
                else None
            ),
            conflict=conflict,
            error_code=ErrorCode.REVISION_CONFLICT,
        )

    def _record_audit(
        self,
        *,
        event_type: str,
        revision: MemoryRevision,
        actor: PrincipalContext,
        reason_code: str,
        policy_decision_ref: str,
        occurred_at: datetime,
        correlation_id: str,
    ) -> str:
        previous = self._audits[-1].event_hash if self._audits else None
        seed = {
            "type": event_type,
            "memory_id": revision.memory_id,
            "revision_id": revision.revision_id,
            "actor": actor.principal_id,
            "occurred_at": occurred_at,
            "correlation_id": correlation_id,
            "nonce": uuid4().hex,
        }
        event_id = f"audit_{canonical_sha256(seed)}"
        payload = {
            "event_id": event_id,
            "event_type": event_type,
            "memory_id": revision.memory_id,
            "revision_id": revision.revision_id,
            "namespace": revision.namespace,
            "actor_principal_ref": actor.principal_id,
            "occurred_at": occurred_at,
            "reason_code": reason_code,
            "policy_decision_ref": policy_decision_ref,
            "previous_event_hash": previous,
        }
        event = AuditEvent(**payload, event_hash=canonical_sha256(payload))
        self._audits.append(event)
        return event.event_id

    def _head_without_permission(self, memory_id: str) -> MemoryRevision:
        self._assert_not_forgotten(memory_id)
        history = self._revisions.get(memory_id, [])
        if not history:
            raise MemoryContractError(ErrorCode.MEMORY_NOT_FOUND, "memory not found")
        return history[-1]

    def _require_permission(
        self,
        actor: PrincipalContext,
        namespace: MemoryNamespace,
        operation: AccessOperation,
    ) -> None:
        decision = self.evaluate_permission(
            actor=actor, namespace=namespace, operation=operation
        )
        if not decision.allowed:
            raise MemoryContractError(decision.error_code or ErrorCode.ACL_DENIED, decision.reason)

    def _assert_not_forgotten(self, memory_id: str) -> None:
        if memory_id in self._tombstones:
            raise MemoryContractError(
                ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE,
                "forgotten content is unavailable",
            )
