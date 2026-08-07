from __future__ import annotations

from ..memory_contracts import (
    AccessOperation,
    AppendRevisionResult,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryRevision,
    PrincipalContext,
    StateEvent,
)
from .fence import MemoryRevisionFence
from .sqlite import SQLiteMemoryStore

_ADMISSIBLE_FENCE_STATES = frozenset(
    {LifecycleState.CANDIDATE, LifecycleState.VERIFIED, LifecycleState.PROMOTED}
)


class MemoryFenceViolation(RuntimeError):
    def __init__(self, reason: str, error_code: ErrorCode) -> None:
        super().__init__(reason)
        self.reason = reason
        self.error_code = error_code


class FencedSQLiteMemoryStore(SQLiteMemoryStore):
    """SQLite Store that atomically fences derived-Memory dependencies."""

    def append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str | None,
        correlation_id: str,
    ) -> AppendRevisionResult:
        if not self._requires_parent_fence(revision):
            return super().append_revision(
                actor=actor,
                revision=revision,
                expected_head_revision_id=expected_head_revision_id,
                correlation_id=correlation_id,
            )

        fences = self._fences_from_revision(revision)
        return self.append_revision_with_parent_fences(
            actor=actor,
            revision=revision,
            expected_head_revision_id=expected_head_revision_id,
            correlation_id=correlation_id,
            parent_fences=fences,
        )

    def append_revision_with_parent_fences(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str | None,
        correlation_id: str,
        parent_fences: tuple[MemoryRevisionFence, ...],
    ) -> AppendRevisionResult:
        if not parent_fences:
            return self._fence_rejected(ErrorCode.PROVENANCE_MISSING)

        def operation() -> AppendRevisionResult:
            violation = self._verify_parent_fences(
                actor=actor,
                revision=revision,
                parent_fences=parent_fences,
            )
            if violation is not None:
                return self._fence_rejected(violation.error_code)

            # SQLiteMemoryStore.append_revision sees the active connection and
            # reuses this exact BEGIN IMMEDIATE transaction for CAS, Audit and
            # Outbox persistence.
            return super(FencedSQLiteMemoryStore, self).append_revision(
                actor=actor,
                revision=revision,
                expected_head_revision_id=expected_head_revision_id,
                correlation_id=correlation_id,
            )

        return self._run_write(operation)

    @staticmethod
    def _requires_parent_fence(revision: MemoryRevision) -> bool:
        return revision.formation_event_ref.startswith("consolidation_")

    @staticmethod
    def _fences_from_revision(
        revision: MemoryRevision,
    ) -> tuple[MemoryRevisionFence, ...]:
        fences: list[MemoryRevisionFence] = []
        hashes = revision.provenance.source_content_hashes
        for ref in revision.provenance.parent_memory_refs:
            memory_id, separator, revision_id = ref.partition("@")
            if separator != "@" or ref not in hashes:
                continue
            fences.append(
                MemoryRevisionFence(
                    memory_id=memory_id,
                    revision_id=revision_id,
                    content_hash=hashes[ref],
                    # Commit-time fencing only needs to prove the parent is
                    # still currently admissible. The exact pre-admission state
                    # remains part of M1C replay evidence.
                    lifecycle_state=LifecycleState.CANDIDATE,
                )
            )
        return tuple(fences)

    def _verify_parent_fences(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        parent_fences: tuple[MemoryRevisionFence, ...],
    ) -> MemoryFenceViolation | None:
        connection = self._active_connection
        if connection is None:
            return MemoryFenceViolation(
                "PARENT_FENCE_TRANSACTION_MISSING",
                ErrorCode.INTEGRITY_FAILED,
            )

        for access_operation in (
            AccessOperation.QUERY,
            AccessOperation.READ_CONTENT,
        ):
            permission = self.evaluate_permission(
                actor=actor,
                namespace=revision.namespace,
                operation=access_operation,
            )
            if not permission.allowed:
                return MemoryFenceViolation(
                    "PARENT_FENCE_AUTHORITY_CHANGED",
                    ErrorCode.ACL_DENIED,
                )

        for fence in parent_fences:
            if connection.execute(
                "SELECT 1 FROM tombstones WHERE memory_id = ?",
                (fence.memory_id,),
            ).fetchone() is not None:
                return MemoryFenceViolation(
                    "PARENT_FENCE_FORGOTTEN",
                    ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE,
                )

            row = connection.execute(
                """
                SELECT r.namespace, r.payload_json,
                       h.revision_id AS head_revision_id
                FROM revisions AS r
                LEFT JOIN heads AS h ON h.memory_id = r.memory_id
                WHERE r.memory_id = ? AND r.revision_id = ?
                """,
                (fence.memory_id, fence.revision_id),
            ).fetchone()
            if row is None or row["head_revision_id"] != fence.revision_id:
                return MemoryFenceViolation(
                    "PARENT_FENCE_HEAD_CHANGED",
                    ErrorCode.REVISION_CONFLICT,
                )
            if row["namespace"] != revision.namespace.canonical:
                return MemoryFenceViolation(
                    "PARENT_FENCE_NAMESPACE_CHANGED",
                    ErrorCode.NAMESPACE_DENIED,
                )

            parent_revision = MemoryRevision.model_validate_json(row["payload_json"])
            if parent_revision.content_hash != fence.content_hash:
                return MemoryFenceViolation(
                    "PARENT_FENCE_HASH_CHANGED",
                    ErrorCode.INTEGRITY_FAILED,
                )

            state_row = connection.execute(
                """
                SELECT payload_json
                FROM state_events
                WHERE memory_id = ? AND revision_id = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (fence.memory_id, fence.revision_id),
            ).fetchone()
            current_state = (
                LifecycleState.CANDIDATE
                if state_row is None
                else StateEvent.model_validate_json(state_row["payload_json"]).to_state
            )
            if current_state not in _ADMISSIBLE_FENCE_STATES:
                return MemoryFenceViolation(
                    "PARENT_FENCE_NOT_ADMISSIBLE",
                    ErrorCode.MEMORY_NOT_EFFECTIVE,
                )

        return None

    @staticmethod
    def _fence_rejected(error_code: ErrorCode) -> AppendRevisionResult:
        return AppendRevisionResult(
            decision=Decision.REJECTED,
            error_code=error_code,
        )
