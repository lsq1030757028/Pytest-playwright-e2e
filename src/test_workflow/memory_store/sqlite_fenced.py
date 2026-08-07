from __future__ import annotations

from ..memory_contracts import (
    AccessOperation,
    AppendRevisionResult,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryRevision,
    PrincipalContext,
    StateEvent,
)
from .fence import MemoryRevisionFence
from .sqlite import SQLiteMemoryStore

_ADMISSIBLE_FENCE_STATES = frozenset(
    {LifecycleState.CANDIDATE, LifecycleState.VERIFIED, LifecycleState.PROMOTED}
)


class MemoryFenceViolation(MemoryContractError):
    def __init__(self, reason: str, *, code: ErrorCode = ErrorCode.REVISION_CONFLICT) -> None:
        super().__init__(code, reason)
        self.reason = reason


class FencedSQLiteMemoryStore(SQLiteMemoryStore):
    """SQLite Store extension that verifies parent dependencies inside append TX."""

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
            raise ValueError("parent_fences must not be empty")

        def operation() -> AppendRevisionResult:
            connection = self._active_connection
            if connection is None:
                raise MemoryContractError(
                    ErrorCode.INTEGRITY_FAILED,
                    "parent fence verification requires an active Store write transaction",
                )

            # Read authority for the parent namespace is re-checked after
            # BEGIN IMMEDIATE and the authoritative Store reload. A concurrent
            # ACL change therefore orders before or after this fenced commit.
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
                    raise MemoryFenceViolation(
                        "PARENT_FENCE_AUTHORITY_CHANGED",
                        code=ErrorCode.ACL_DENIED,
                    )

            for fence in parent_fences:
                tombstone = connection.execute(
                    "SELECT 1 FROM tombstones WHERE memory_id = ?",
                    (fence.memory_id,),
                ).fetchone()
                if tombstone is not None:
                    raise MemoryFenceViolation(
                        "PARENT_FENCE_FORGOTTEN",
                        code=ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE,
                    )

                row = connection.execute(
                    """
                    SELECT r.payload_json, h.revision_id AS head_revision_id
                    FROM revisions AS r
                    LEFT JOIN heads AS h ON h.memory_id = r.memory_id
                    WHERE r.memory_id = ? AND r.revision_id = ?
                    """,
                    (fence.memory_id, fence.revision_id),
                ).fetchone()
                if row is None:
                    raise MemoryFenceViolation("PARENT_FENCE_MISSING")
                if row["head_revision_id"] != fence.revision_id:
                    raise MemoryFenceViolation("PARENT_FENCE_HEAD_CHANGED")

                parent_revision = MemoryRevision.model_validate_json(row["payload_json"])
                if parent_revision.content_hash != fence.content_hash:
                    raise MemoryFenceViolation(
                        "PARENT_FENCE_HASH_CHANGED",
                        code=ErrorCode.INTEGRITY_FAILED,
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
                if current_state != fence.lifecycle_state:
                    raise MemoryFenceViolation("PARENT_FENCE_LIFECYCLE_CHANGED")
                if current_state not in _ADMISSIBLE_FENCE_STATES:
                    raise MemoryFenceViolation(
                        "PARENT_FENCE_NOT_ADMISSIBLE",
                        code=ErrorCode.MEMORY_NOT_EFFECTIVE,
                    )

            # SQLiteMemoryStore.append_revision sees the active connection and
            # reuses this exact transaction for CAS, audit and Outbox persistence.
            return super(FencedSQLiteMemoryStore, self).append_revision(
                actor=actor,
                revision=revision,
                expected_head_revision_id=expected_head_revision_id,
                correlation_id=correlation_id,
            )

        return self._run_write(operation)
