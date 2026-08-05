from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .models import (
    AccessOperation,
    AclEntry,
    AppendRevisionResult,
    AuditEvent,
    CompatibilityContext,
    ForgetTombstone,
    LifecycleState,
    MemoryNamespace,
    MemoryRevision,
    MutationResult,
    PermissionDecision,
    PrincipalContext,
    ReadMode,
    StateEvent,
)


@runtime_checkable
class MemoryRevisionPort(Protocol):
    def append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str | None,
        correlation_id: str,
    ) -> AppendRevisionResult: ...

    def get_revision(
        self, *, actor: PrincipalContext, memory_id: str, revision_id: str
    ) -> MemoryRevision: ...

    def get_head_revision(
        self, *, actor: PrincipalContext, memory_id: str
    ) -> MemoryRevision: ...

    def list_revision_history(
        self, *, actor: PrincipalContext, memory_id: str
    ) -> tuple[MemoryRevision, ...]: ...

    def compare_and_append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str,
        correlation_id: str,
    ) -> AppendRevisionResult: ...


@runtime_checkable
class MemoryStatePort(Protocol):
    def append_state_event(
        self, *, actor: PrincipalContext, event: StateEvent, correlation_id: str
    ) -> MutationResult: ...

    def get_effective_state(self, *, memory_id: str) -> LifecycleState: ...

    def list_state_history(self, *, memory_id: str) -> tuple[StateEvent, ...]: ...


@runtime_checkable
class MemoryAclPort(Protocol):
    def evaluate_permission(
        self,
        *,
        actor: PrincipalContext,
        namespace: MemoryNamespace,
        operation: AccessOperation,
    ) -> PermissionDecision: ...

    def append_acl_event(
        self,
        *,
        actor: PrincipalContext,
        entry: AclEntry,
        correlation_id: str,
    ) -> MutationResult: ...

    def list_effective_acl(self, *, namespace: MemoryNamespace) -> tuple[AclEntry, ...]: ...


@runtime_checkable
class MemoryQueryPort(Protocol):
    def query_exact_authorized_namespaces(
        self,
        *,
        actor: PrincipalContext,
        namespaces: tuple[MemoryNamespace, ...],
        read_mode: ReadMode,
        compatibility_context: CompatibilityContext | None = None,
        now: datetime | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[tuple[MemoryRevision, ...], str | None]: ...

    def filter_by_metadata(
        self,
        revisions: tuple[MemoryRevision, ...],
        *,
        memory_kind: str | None = None,
        schema_version: str | None = None,
    ) -> tuple[MemoryRevision, ...]: ...

    def paginate_deterministically(
        self,
        revisions: tuple[MemoryRevision, ...],
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[tuple[MemoryRevision, ...], str | None]: ...


@runtime_checkable
class MemoryAuditPort(Protocol):
    def append_audit_event(self, event: AuditEvent) -> str: ...

    def list_audit_events(self, *, memory_id: str | None = None) -> tuple[AuditEvent, ...]: ...

    def verify_event_chain(self) -> bool: ...


@runtime_checkable
class MemoryMaintenancePort(Protocol):
    def expire_due_memories(
        self, *, actor: PrincipalContext, now: datetime, correlation_id: str
    ) -> tuple[str, ...]: ...

    def revoke_memory(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        reason_code: str,
        policy_decision_ref: str,
        correlation_id: str,
    ) -> MutationResult: ...

    def forget_memory(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        reason_code: str,
        policy_decision_ref: str,
        correlation_id: str,
    ) -> ForgetTombstone: ...

    def verify_cache_and_index_invalidation(self, *, memory_id: str) -> bool: ...
