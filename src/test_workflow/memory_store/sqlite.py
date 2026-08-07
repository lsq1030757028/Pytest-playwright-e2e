from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from ..memory_contracts import (
    AccessOperation,
    AclEntry,
    AppendRevisionResult,
    AuditEvent,
    CompatibilityContext,
    DeterministicMemoryReference,
    ErrorCode,
    ForgetTombstone,
    MemoryContractError,
    MemoryNamespace,
    MemoryRevision,
    MutationResult,
    PrincipalContext,
    PromotionRequest,
    ReadMode,
    StateEvent,
    canonical_sha256,
)

T = TypeVar("T")
_SCHEMA_VERSION = "1"


class SQLiteMemoryStore(DeterministicMemoryReference):
    """Durable M1B reference profile backed by SQLite WAL.

    Domain decisions remain owned by the hardened M1A reference adapter. This
    class adds transactional persistence, restart recovery, an append-only
    outbox, and database integrity checks without widening Memory authority.
    """

    def __init__(
        self,
        db_path: Path | str,
        *,
        resolved_sources: dict[str, str] | None = None,
        resolved_evidence: Iterable[str] = (),
        resolved_benchmarks: Iterable[str] = (),
        initial_acl: Iterable[AclEntry] = (),
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._active_connection: sqlite3.Connection | None = None
        self._read_depth = 0
        super().__init__(
            resolved_sources=resolved_sources,
            resolved_evidence=resolved_evidence,
            resolved_benchmarks=resolved_benchmarks,
            initial_acl=(),
        )
        self._initialize_database(tuple(initial_acl))
        self._reload_from_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize_database(self, initial_acl: tuple[AclEntry, ...]) -> None:
        with closing(self._connect()) as connection:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise MemoryContractError(
                    ErrorCode.INTEGRITY_FAILED,
                    f"SQLite WAL is required, got {mode!r}",
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS revisions (
                    memory_id TEXT NOT NULL,
                    revision_id TEXT PRIMARY KEY,
                    revision_number INTEGER NOT NULL,
                    namespace TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_revisions_memory_number
                    ON revisions(memory_id, revision_number);

                CREATE TABLE IF NOT EXISTS heads (
                    memory_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL UNIQUE,
                    revision_number INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    state_event_id TEXT NOT NULL UNIQUE,
                    memory_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_state_events_memory_sequence
                    ON state_events(memory_id, sequence);

                CREATE TABLE IF NOT EXISTS acl_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_acl_events_namespace_sequence
                    ON acl_events(namespace, sequence);

                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    memory_id TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    previous_event_hash TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    memory_id TEXT,
                    request_fingerprint TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tombstones (
                    memory_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS invalidations (
                    memory_id TEXT PRIMARY KEY,
                    invalidated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outbox (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    memory_id TEXT,
                    namespace TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    applied INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0, 1))
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_pending
                    ON outbox(applied, sequence);
                """
            )
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                        (_SCHEMA_VERSION,),
                    )
                elif row["value"] != _SCHEMA_VERSION:
                    raise MemoryContractError(
                        ErrorCode.INTEGRITY_FAILED,
                        "unsupported SQLite Memory schema version",
                    )

                acl_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM acl_events"
                ).fetchone()["count"]
                if acl_count == 0:
                    for entry in initial_acl:
                        connection.execute(
                            """
                            INSERT INTO acl_events(namespace, rule_id, payload_json)
                            VALUES (?, ?, ?)
                            """,
                            (
                                entry.namespace.canonical,
                                entry.rule_id,
                                entry.model_dump_json(),
                            ),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _clear_runtime_state(self) -> None:
        self._revisions = {}
        self._states = {}
        self._acl = {}
        self._audits = []
        self._idempotency = {}
        self._tombstones = {}
        self._invalidated = set()

    def _reload_from_connection(self, connection: sqlite3.Connection) -> None:
        self._clear_runtime_state()

        for row in connection.execute(
            """
            SELECT payload_json
            FROM revisions
            ORDER BY memory_id, revision_number, revision_id
            """
        ):
            revision = MemoryRevision.model_validate_json(row["payload_json"])
            self._revisions.setdefault(revision.memory_id, []).append(revision)

        for row in connection.execute(
            "SELECT payload_json FROM state_events ORDER BY sequence"
        ):
            event = StateEvent.model_validate_json(row["payload_json"])
            self._states.setdefault(event.memory_id, []).append(event)

        for row in connection.execute(
            "SELECT payload_json FROM acl_events ORDER BY sequence"
        ):
            entry = AclEntry.model_validate_json(row["payload_json"])
            self._acl.setdefault(entry.namespace.canonical, []).append(entry)

        for row in connection.execute(
            "SELECT payload_json FROM audit_events ORDER BY sequence"
        ):
            self._audits.append(AuditEvent.model_validate_json(row["payload_json"]))

        for row in connection.execute(
            """
            SELECT idempotency_key, request_fingerprint, result_json
            FROM idempotency
            """
        ):
            self._idempotency[row["idempotency_key"]] = (
                row["request_fingerprint"],
                AppendRevisionResult.model_validate_json(row["result_json"]),
            )

        for row in connection.execute("SELECT payload_json FROM tombstones"):
            tombstone = ForgetTombstone.model_validate_json(row["payload_json"])
            self._tombstones[tombstone.memory_id] = tombstone

        for row in connection.execute("SELECT memory_id FROM invalidations"):
            self._invalidated.add(row["memory_id"])

        forgotten_with_content = set(self._tombstones) & set(self._revisions)
        if forgotten_with_content:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "forgotten Memory still has primary content",
            )

        persisted_heads = {
            row["memory_id"]: (row["revision_id"], row["revision_number"])
            for row in connection.execute(
                "SELECT memory_id, revision_id, revision_number FROM heads"
            )
        }
        expected_heads = {
            memory_id: (history[-1].revision_id, history[-1].revision_number)
            for memory_id, history in self._revisions.items()
            if history
        }
        if persisted_heads != expected_heads:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "persisted Memory heads do not match immutable revision history",
            )
        if not super().verify_event_chain():
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "persisted Memory audit chain is invalid",
            )

    def _reload_from_database(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            try:
                self._reload_from_connection(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _capture_state(self) -> dict[str, Any]:
        return {
            "revision_ids": {
                revision.revision_id
                for history in self._revisions.values()
                for revision in history
            },
            "state_ids": {
                event.state_event_id
                for events in self._states.values()
                for event in events
            },
            "acl_counts": {
                namespace: len(entries) for namespace, entries in self._acl.items()
            },
            "audit_ids": {event.event_id for event in self._audits},
            "idempotency_keys": set(self._idempotency),
            "tombstone_ids": set(self._tombstones),
            "invalidated_ids": set(self._invalidated),
        }

    def _insert_outbox(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        memory_id: str | None,
        namespace: str | None,
        identity: str,
        payload: dict[str, Any],
    ) -> None:
        event_seed = {
            "event_type": event_type,
            "memory_id": memory_id,
            "namespace": namespace,
            "identity": identity,
        }
        event_id = f"outbox_{canonical_sha256(event_seed)}"
        connection.execute(
            """
            INSERT OR IGNORE INTO outbox(
                event_id, event_type, memory_id, namespace,
                payload_json, created_at, applied
            ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                event_id,
                event_type,
                memory_id,
                namespace,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                datetime.now(UTC).isoformat(),
            ),
        )

    def _persist_delta(
        self,
        connection: sqlite3.Connection,
        before: dict[str, Any],
    ) -> None:
        before_revision_ids: set[str] = before["revision_ids"]
        for history in self._revisions.values():
            for revision in history:
                if revision.revision_id in before_revision_ids:
                    continue
                connection.execute(
                    """
                    INSERT INTO revisions(
                        memory_id, revision_id, revision_number, namespace, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        revision.memory_id,
                        revision.revision_id,
                        revision.revision_number,
                        revision.namespace.canonical,
                        revision.model_dump_json(),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO heads(memory_id, revision_id, revision_number)
                    VALUES (?, ?, ?)
                    ON CONFLICT(memory_id) DO UPDATE SET
                        revision_id = excluded.revision_id,
                        revision_number = excluded.revision_number
                    """,
                    (
                        revision.memory_id,
                        revision.revision_id,
                        revision.revision_number,
                    ),
                )
                self._insert_outbox(
                    connection,
                    event_type="REVISION_COMMITTED",
                    memory_id=revision.memory_id,
                    namespace=revision.namespace.canonical,
                    identity=revision.revision_id,
                    payload={
                        "memory_id": revision.memory_id,
                        "revision_id": revision.revision_id,
                        "revision_number": revision.revision_number,
                        "content_hash": revision.content_hash,
                    },
                )

        before_state_ids: set[str] = before["state_ids"]
        for memory_id, events in self._states.items():
            for event in events:
                if event.state_event_id in before_state_ids:
                    continue
                connection.execute(
                    """
                    INSERT INTO state_events(
                        state_event_id, memory_id, revision_id, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        event.state_event_id,
                        event.memory_id,
                        event.revision_id,
                        event.model_dump_json(),
                    ),
                )
                history = self._revisions.get(memory_id)
                namespace = history[-1].namespace.canonical if history else None
                self._insert_outbox(
                    connection,
                    event_type="STATE_COMMITTED",
                    memory_id=event.memory_id,
                    namespace=namespace,
                    identity=event.state_event_id,
                    payload={
                        "memory_id": event.memory_id,
                        "revision_id": event.revision_id,
                        "state_event_id": event.state_event_id,
                        "to_state": event.to_state.value,
                    },
                )

        before_acl_counts: dict[str, int] = before["acl_counts"]
        for namespace, entries in self._acl.items():
            start = before_acl_counts.get(namespace, 0)
            for offset, entry in enumerate(entries[start:], start=start + 1):
                connection.execute(
                    """
                    INSERT INTO acl_events(namespace, rule_id, payload_json)
                    VALUES (?, ?, ?)
                    """,
                    (namespace, entry.rule_id, entry.model_dump_json()),
                )
                self._insert_outbox(
                    connection,
                    event_type="ACL_COMMITTED",
                    memory_id=None,
                    namespace=namespace,
                    identity=f"{entry.rule_id}:{offset}",
                    payload={
                        "namespace": namespace,
                        "rule_id": entry.rule_id,
                        "effect": entry.effect.value,
                    },
                )

        before_audit_ids: set[str] = before["audit_ids"]
        for event in self._audits:
            if event.event_id in before_audit_ids:
                continue
            connection.execute(
                """
                INSERT INTO audit_events(
                    event_id, memory_id, event_hash, previous_event_hash, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.memory_id,
                    event.event_hash,
                    event.previous_event_hash,
                    event.model_dump_json(),
                ),
            )

        before_idempotency: set[str] = before["idempotency_keys"]
        for key, (fingerprint, result) in self._idempotency.items():
            if key in before_idempotency:
                continue
            memory_id = result.revision.memory_id if result.revision is not None else None
            if memory_id is None and result.conflict is not None:
                memory_id = result.conflict.memory_id
            connection.execute(
                """
                INSERT INTO idempotency(
                    idempotency_key, memory_id, request_fingerprint, result_json
                ) VALUES (?, ?, ?, ?)
                """,
                (key, memory_id, fingerprint, result.model_dump_json()),
            )

        before_tombstones: set[str] = before["tombstone_ids"]
        for memory_id, tombstone in self._tombstones.items():
            if memory_id in before_tombstones:
                continue
            connection.execute(
                """
                INSERT INTO tombstones(memory_id, payload_json)
                VALUES (?, ?)
                """,
                (memory_id, tombstone.model_dump_json()),
            )
            connection.execute("DELETE FROM heads WHERE memory_id = ?", (memory_id,))
            connection.execute("DELETE FROM revisions WHERE memory_id = ?", (memory_id,))
            connection.execute("DELETE FROM idempotency WHERE memory_id = ?", (memory_id,))
            self._idempotency = {
                key: value
                for key, value in self._idempotency.items()
                if not (
                    value[1].revision is not None
                    and value[1].revision.memory_id == memory_id
                )
                and not (
                    value[1].conflict is not None
                    and value[1].conflict.memory_id == memory_id
                )
            }
            self._insert_outbox(
                connection,
                event_type="FORGET_COMMITTED",
                memory_id=memory_id,
                namespace=None,
                identity=memory_id,
                payload=tombstone.model_dump(mode="json"),
            )

        before_invalidated: set[str] = before["invalidated_ids"]
        for memory_id in self._invalidated - before_invalidated:
            connection.execute(
                """
                INSERT OR IGNORE INTO invalidations(memory_id, invalidated_at)
                VALUES (?, ?)
                """,
                (memory_id, datetime.now(UTC).isoformat()),
            )

    def _run_write(self, operation: Callable[[], T]) -> T:
        if self._active_connection is not None:
            return operation()
        with self._lock:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._active_connection = connection
                try:
                    self._reload_from_connection(connection)
                    before = self._capture_state()
                    result = operation()
                    self._persist_delta(connection, before)
                    connection.commit()
                    return result
                except Exception:
                    connection.rollback()
                    self._active_connection = None
                    self._reload_from_database()
                    raise
                finally:
                    self._active_connection = None

    def _run_read(self, operation: Callable[[], T]) -> T:
        if self._active_connection is not None or self._read_depth > 0:
            return operation()
        with self._lock:
            self._reload_from_database()
            self._read_depth += 1
            try:
                return operation()
            finally:
                self._read_depth -= 1

    def append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str | None,
        correlation_id: str,
    ) -> AppendRevisionResult:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).append_revision(
                actor=actor,
                revision=revision,
                expected_head_revision_id=expected_head_revision_id,
                correlation_id=correlation_id,
            )
        )

    def compare_and_append_revision(
        self,
        *,
        actor: PrincipalContext,
        revision: MemoryRevision,
        expected_head_revision_id: str,
        correlation_id: str,
    ) -> AppendRevisionResult:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).compare_and_append_revision(
                actor=actor,
                revision=revision,
                expected_head_revision_id=expected_head_revision_id,
                correlation_id=correlation_id,
            )
        )

    def append_state_event(
        self,
        *,
        actor: PrincipalContext,
        event: StateEvent,
        correlation_id: str,
    ) -> MutationResult:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).append_state_event(
                actor=actor,
                event=event,
                correlation_id=correlation_id,
            )
        )

    def append_acl_event(
        self,
        *,
        actor: PrincipalContext,
        entry: AclEntry,
        correlation_id: str,
    ) -> MutationResult:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).append_acl_event(
                actor=actor,
                entry=entry,
                correlation_id=correlation_id,
            )
        )

    def append_audit_event(self, event: AuditEvent) -> str:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).append_audit_event(event)
        )

    def promote(
        self,
        *,
        actor: PrincipalContext,
        request: PromotionRequest,
        correlation_id: str,
    ) -> MutationResult:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).promote(
                actor=actor,
                request=request,
                correlation_id=correlation_id,
            )
        )

    def expire_due_memories(
        self,
        *,
        actor: PrincipalContext,
        now: datetime,
        correlation_id: str,
    ) -> tuple[str, ...]:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).expire_due_memories(
                actor=actor,
                now=now,
                correlation_id=correlation_id,
            )
        )

    def revoke_memory(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        reason_code: str,
        policy_decision_ref: str,
        correlation_id: str,
    ) -> MutationResult:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).revoke_memory(
                actor=actor,
                memory_id=memory_id,
                reason_code=reason_code,
                policy_decision_ref=policy_decision_ref,
                correlation_id=correlation_id,
            )
        )

    def forget_memory(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        reason_code: str,
        policy_decision_ref: str,
        correlation_id: str,
    ) -> ForgetTombstone:
        return self._run_write(
            lambda: super(SQLiteMemoryStore, self).forget_memory(
                actor=actor,
                memory_id=memory_id,
                reason_code=reason_code,
                policy_decision_ref=policy_decision_ref,
                correlation_id=correlation_id,
            )
        )

    def get_revision(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
        revision_id: str,
    ) -> MemoryRevision:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).get_revision(
                actor=actor,
                memory_id=memory_id,
                revision_id=revision_id,
            )
        )

    def get_head_revision(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
    ) -> MemoryRevision:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).get_head_revision(
                actor=actor,
                memory_id=memory_id,
            )
        )

    def list_revision_history(
        self,
        *,
        actor: PrincipalContext,
        memory_id: str,
    ) -> tuple[MemoryRevision, ...]:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).list_revision_history(
                actor=actor,
                memory_id=memory_id,
            )
        )

    def get_effective_state(self, *, memory_id: str):
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).get_effective_state(memory_id=memory_id)
        )

    def list_state_history(self, *, memory_id: str) -> tuple[StateEvent, ...]:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).list_state_history(memory_id=memory_id)
        )

    def evaluate_permission(
        self,
        *,
        actor: PrincipalContext,
        namespace: MemoryNamespace,
        operation: AccessOperation,
    ):
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).evaluate_permission(
                actor=actor,
                namespace=namespace,
                operation=operation,
            )
        )

    def list_effective_acl(self, *, namespace: MemoryNamespace) -> tuple[AclEntry, ...]:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).list_effective_acl(namespace=namespace)
        )

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
    ) -> tuple[tuple[MemoryRevision, ...], str | None]:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).query_exact_authorized_namespaces(
                actor=actor,
                namespaces=namespaces,
                read_mode=read_mode,
                compatibility_context=compatibility_context,
                now=now,
                cursor=cursor,
                limit=limit,
            )
        )

    def list_audit_events(
        self,
        *,
        memory_id: str | None = None,
    ) -> tuple[AuditEvent, ...]:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).list_audit_events(memory_id=memory_id)
        )

    def verify_event_chain(self) -> bool:
        return self._run_read(lambda: super(SQLiteMemoryStore, self).verify_event_chain())

    def verify_cache_and_index_invalidation(self, *, memory_id: str) -> bool:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).verify_cache_and_index_invalidation(
                memory_id=memory_id
            )
        )

    def get_tombstone(self, *, memory_id: str) -> ForgetTombstone | None:
        return self._run_read(
            lambda: super(SQLiteMemoryStore, self).get_tombstone(memory_id=memory_id)
        )

    def journal_mode(self) -> str:
        with closing(self._connect()) as connection:
            return str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def pending_outbox(self, *, limit: int = 100) -> tuple[dict[str, Any], ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_id, event_type, memory_id, namespace, payload_json
                FROM outbox
                WHERE applied = 0
                ORDER BY sequence
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(
            {
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "memory_id": row["memory_id"],
                "namespace": row["namespace"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        )

    def primary_content_rows(self, *, memory_id: str) -> int:
        with closing(self._connect()) as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM revisions WHERE memory_id = ?",
                    (memory_id,),
                ).fetchone()[0]
            )
