from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..memory_contracts import ErrorCode, MemoryContractError, canonical_sha256
from .sqlite import SQLiteMemoryStore


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoreManifest(FrozenModel):
    schema_version: str
    revision_refs: tuple[str, ...]
    revision_hashes: tuple[str, ...]
    head_pairs: tuple[str, ...]
    state_event_hashes: tuple[str, ...]
    acl_event_digests: tuple[str, ...]
    audit_event_hashes: tuple[str, ...]
    idempotency_digests: tuple[str, ...]
    tombstone_digests: tuple[str, ...]
    outbox_event_digests: tuple[str, ...]
    formation_event_digests: tuple[str, ...]
    formation_idempotency_digests: tuple[str, ...]
    formation_replay_digests: tuple[str, ...]
    consolidation_event_digests: tuple[str, ...]
    consolidation_idempotency_digests: tuple[str, ...]
    consolidation_replay_digests: tuple[str, ...]
    contamination_record_digests: tuple[str, ...]
    contamination_checkpoint_digests: tuple[str, ...]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class MigrationReport(FrozenModel):
    source_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    equivalent: bool
    target_path: str
    migration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SQLiteMigrationController:
    """Shadow-copy and guarded cutover for the SQLite reference profile.

    The source remains the rollback path. Cutover is allowed only when source
    and target manifests are byte/hash-equivalent. Rollback is blocked if the
    target diverged after cutover, preventing loss or resurrection of newer
    governed state (especially Forget Tombstones and M1C formation evidence).
    """

    def __init__(self, source_path: Path | str) -> None:
        self.source_path = Path(source_path)
        self.target_path: Path | None = None
        self.active_path = self.source_path
        self._migration_report: MigrationReport | None = None

    @staticmethod
    def manifest(db_path: Path | str) -> StoreManifest:
        path = Path(db_path)
        with closing(sqlite3.connect(path)) as connection:
            connection.row_factory = sqlite3.Row
            schema_row = connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            if schema_row is None:
                raise MemoryContractError(
                    ErrorCode.INTEGRITY_FAILED,
                    "Memory Store schema version is missing",
                )
            revision_rows = connection.execute(
                """
                SELECT memory_id, revision_id, payload_json
                FROM revisions
                ORDER BY memory_id, revision_number, revision_id
                """
            ).fetchall()
            head_rows = connection.execute(
                "SELECT memory_id, revision_id FROM heads ORDER BY memory_id"
            ).fetchall()
            state_rows = connection.execute(
                "SELECT payload_json FROM state_events ORDER BY sequence"
            ).fetchall()
            acl_rows = connection.execute(
                """
                SELECT namespace, rule_id, payload_json
                FROM acl_events
                ORDER BY sequence
                """
            ).fetchall()
            audit_rows = connection.execute(
                "SELECT event_hash FROM audit_events ORDER BY sequence"
            ).fetchall()
            idempotency_rows = connection.execute(
                """
                SELECT idempotency_key, memory_id, request_fingerprint, result_json
                FROM idempotency
                ORDER BY idempotency_key
                """
            ).fetchall()
            tombstone_rows = connection.execute(
                "SELECT memory_id, payload_json FROM tombstones ORDER BY memory_id"
            ).fetchall()
            outbox_rows = connection.execute(
                """
                SELECT event_id, event_type, memory_id, namespace,
                       payload_json, applied
                FROM outbox
                ORDER BY sequence
                """
            ).fetchall()

            formation_event_digests = _optional_row_digests(
                connection,
                table="formation_events",
                columns=("event_id", "request_digest", "event_hash", "payload_json"),
                order_by="event_id",
            )
            formation_idempotency_digests = _optional_row_digests(
                connection,
                table="formation_idempotency",
                columns=(
                    "idempotency_key",
                    "request_fingerprint",
                    "request_digest",
                    "state",
                    "result_json",
                ),
                order_by="idempotency_key",
            )
            formation_replay_digests = _optional_row_digests(
                connection,
                table="formation_replay",
                columns=("request_digest", "manifest_digest", "payload_json"),
                order_by="request_digest",
            )
            consolidation_event_digests = _optional_row_digests(
                connection,
                table="consolidation_events",
                columns=("event_id", "request_digest", "event_hash", "payload_json"),
                order_by="event_id",
            )
            consolidation_idempotency_digests = _optional_row_digests(
                connection,
                table="consolidation_idempotency",
                columns=(
                    "idempotency_key",
                    "request_fingerprint",
                    "request_digest",
                    "state",
                    "result_json",
                ),
                order_by="idempotency_key",
            )
            consolidation_replay_digests = _optional_row_digests(
                connection,
                table="consolidation_replay",
                columns=("request_digest", "manifest_digest", "payload_json"),
                order_by="request_digest",
            )
            contamination_record_digests = _optional_row_digests(
                connection,
                table="memory_contamination",
                columns=(
                    "memory_ref",
                    "contamination_class",
                    "evidence_digest",
                    "inherited_from_ref",
                    "record_digest",
                ),
                order_by="memory_ref, contamination_class",
            )
            contamination_checkpoint_digests = _optional_row_digests(
                connection,
                table="memory_contamination_checkpoints",
                columns=(
                    "manifest_digest",
                    "previous_checkpoint_hash",
                    "checkpoint_hash",
                ),
                order_by="sequence",
            )

        revision_payloads = [json.loads(row["payload_json"]) for row in revision_rows]
        revision_refs = tuple(
            f"{payload['memory_id']}@{payload['revision_id']}"
            for payload in revision_payloads
        )
        revision_hashes = tuple(payload["content_hash"] for payload in revision_payloads)
        head_pairs = tuple(
            f"{row['memory_id']}@{row['revision_id']}" for row in head_rows
        )
        state_event_hashes = tuple(
            json.loads(row["payload_json"])["event_hash"] for row in state_rows
        )
        acl_event_digests = tuple(
            canonical_sha256(
                {
                    "namespace": row["namespace"],
                    "rule_id": row["rule_id"],
                    "payload": json.loads(row["payload_json"]),
                }
            )
            for row in acl_rows
        )
        audit_event_hashes = tuple(row["event_hash"] for row in audit_rows)
        idempotency_digests = tuple(
            canonical_sha256(
                {
                    "idempotency_key": row["idempotency_key"],
                    "memory_id": row["memory_id"],
                    "request_fingerprint": row["request_fingerprint"],
                    "result": json.loads(row["result_json"]),
                }
            )
            for row in idempotency_rows
        )
        tombstone_digests = tuple(
            canonical_sha256(
                {
                    "memory_id": row["memory_id"],
                    "payload": json.loads(row["payload_json"]),
                }
            )
            for row in tombstone_rows
        )
        outbox_event_digests = tuple(
            canonical_sha256(
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "memory_id": row["memory_id"],
                    "namespace": row["namespace"],
                    "payload": json.loads(row["payload_json"]),
                    "applied": int(row["applied"]),
                }
            )
            for row in outbox_rows
        )
        payload = {
            "schema_version": str(schema_row["value"]),
            "revision_refs": revision_refs,
            "revision_hashes": revision_hashes,
            "head_pairs": head_pairs,
            "state_event_hashes": state_event_hashes,
            "acl_event_digests": acl_event_digests,
            "audit_event_hashes": audit_event_hashes,
            "idempotency_digests": idempotency_digests,
            "tombstone_digests": tombstone_digests,
            "outbox_event_digests": outbox_event_digests,
            "formation_event_digests": formation_event_digests,
            "formation_idempotency_digests": formation_idempotency_digests,
            "formation_replay_digests": formation_replay_digests,
            "consolidation_event_digests": consolidation_event_digests,
            "consolidation_idempotency_digests": consolidation_idempotency_digests,
            "consolidation_replay_digests": consolidation_replay_digests,
            "contamination_record_digests": contamination_record_digests,
            "contamination_checkpoint_digests": contamination_checkpoint_digests,
        }
        return StoreManifest(**payload, digest=canonical_sha256(payload))

    def migrate(self, target_path: Path | str) -> MigrationReport:
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() == self.source_path.resolve():
            raise ValueError("migration target must differ from source")

        _verify_optional_m1c_integrity(self.source_path)
        with closing(sqlite3.connect(self.source_path)) as source, closing(
            sqlite3.connect(target)
        ) as destination:
            source.backup(destination)

        # Loading the copied Store proves schema, Head/history and Audit chain
        # integrity. The optional M1C verifier additionally proves formation,
        # consolidation, replay and contamination evidence when those surfaces
        # exist in this Store.
        SQLiteMemoryStore(target)
        _verify_optional_m1c_integrity(target)
        source_manifest = self.manifest(self.source_path)
        target_manifest = self.manifest(target)
        equivalent = source_manifest.digest == target_manifest.digest
        payload = {
            "source_manifest_digest": source_manifest.digest,
            "target_manifest_digest": target_manifest.digest,
            "equivalent": equivalent,
            "target_path": str(target),
        }
        report = MigrationReport(**payload, migration_digest=canonical_sha256(payload))
        self.target_path = target
        self._migration_report = report
        return report

    def cutover(self) -> Path:
        if self.target_path is None or self._migration_report is None:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "migration target has not been verified",
            )
        _verify_optional_m1c_integrity(self.source_path)
        _verify_optional_m1c_integrity(self.target_path)
        current_source = self.manifest(self.source_path)
        current_target = self.manifest(self.target_path)
        if (
            not self._migration_report.equivalent
            or current_source.digest != current_target.digest
        ):
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "source and target diverged before cutover",
            )
        self.active_path = self.target_path
        return self.active_path

    def rollback(self) -> Path:
        if self.target_path is None:
            self.active_path = self.source_path
            return self.active_path
        _verify_optional_m1c_integrity(self.source_path)
        _verify_optional_m1c_integrity(self.target_path)
        source_manifest = self.manifest(self.source_path)
        target_manifest = self.manifest(self.target_path)
        if source_manifest.digest != target_manifest.digest:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "rollback blocked because target contains governed state absent from source",
            )
        self.active_path = self.source_path
        return self.active_path


def _optional_row_digests(
    connection: sqlite3.Connection,
    *,
    table: str,
    columns: tuple[str, ...],
    order_by: str,
) -> tuple[str, ...]:
    if not _table_exists(connection, table):
        return ()
    column_sql = ", ".join(columns)
    rows = connection.execute(
        f"SELECT {column_sql} FROM {table} ORDER BY {order_by}"
    ).fetchall()
    return tuple(
        canonical_sha256({column: row[column] for column in columns})
        for row in rows
    )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def _verify_optional_m1c_integrity(db_path: Path | str) -> None:
    # Lazy import avoids an import cycle during memory_store package startup.
    from ..memory_formation.integrity import verify_formation_integrity

    verify_formation_integrity(db_path)
