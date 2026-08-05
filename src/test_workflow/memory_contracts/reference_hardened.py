from __future__ import annotations

from pydantic import ValidationError

from .canonical import canonical_sha256
from .models import (
    AccessOperation,
    AppendRevisionResult,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryRevision,
    PrincipalContext,
)
from .reference import DeterministicMemoryReference as _ReferenceBase


class DeterministicMemoryReference(_ReferenceBase):
    """Security-hardened M1A reference adapter.

    A newly appended immutable revision always starts at CANDIDATE. Idempotency
    replays are bound to the authenticated actor and complete CAS request, and
    current permission is re-evaluated before an earlier result can be replayed.
    """

    def append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str | None,
        correlation_id: str,
    ) -> AppendRevisionResult:
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
        if revision.memory_id in self._tombstones:
            return AppendRevisionResult(
                decision=Decision.REJECTED,
                effective_state=LifecycleState.FORGOTTEN,
                error_code=ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE,
            )

        request_fingerprint = canonical_sha256(
            {
                "actor_principal_id": actor.principal_id,
                "expected_head_revision_id": expected_head_revision_id,
                "revision": revision.model_dump(mode="json"),
            }
        )
        existing = self._idempotency.get(revision.idempotency_key)
        if existing is not None:
            existing_fingerprint, result = existing
            if existing_fingerprint != request_fingerprint:
                raise MemoryContractError(
                    ErrorCode.DUPLICATE_IDEMPOTENCY_KEY,
                    "idempotency key was reused with a different authenticated CAS request",
                )
            return result.model_copy(update={"decision": Decision.IDEMPOTENT_REPLAY})

        try:
            revision = MemoryRevision.model_validate(revision.model_dump(mode="python"))
        except ValidationError:
            return AppendRevisionResult(
                decision=Decision.REJECTED,
                error_code=ErrorCode.INVALID_SCHEMA,
            )

        provenance_error = self._validate_provenance(revision)
        if provenance_error is not None:
            result = AppendRevisionResult(
                decision=Decision.REJECTED,
                error_code=ErrorCode.PROVENANCE_MISSING,
            )
            self._idempotency[revision.idempotency_key] = (request_fingerprint, result)
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
                self._idempotency[revision.idempotency_key] = (
                    request_fingerprint,
                    result,
                )
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
                self._idempotency[revision.idempotency_key] = (
                    request_fingerprint,
                    result,
                )
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
        self._idempotency[revision.idempotency_key] = (request_fingerprint, result)
        return result

    def get_effective_state(self, *, memory_id: str) -> LifecycleState:
        if memory_id in self._tombstones:
            return LifecycleState.FORGOTTEN
        history = self._revisions.get(memory_id, [])
        if not history:
            return LifecycleState.CANDIDATE
        head_revision_id = history[-1].revision_id
        for event in reversed(self._states.get(memory_id, [])):
            if event.revision_id == head_revision_id:
                return event.to_state
        return LifecycleState.CANDIDATE
