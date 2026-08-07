from __future__ import annotations

import sqlite3
from contextlib import closing
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..memory_contracts import (
    ErrorCode,
    MemoryContractError,
    MemoryRevision,
    canonical_sha256,
)


class ContaminationClass(StrEnum):
    EVALUATOR_ONLY = "EVALUATOR_ONLY"
    HIDDEN_HOLDOUT = "HIDDEN_HOLDOUT"
    SENSITIVE_FORBIDDEN = "SENSITIVE_FORBIDDEN"
    BENCHMARK_ANSWER = "BENCHMARK_ANSWER"


class ContaminationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_ref: str
    contamination_class: ContaminationClass
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inherited_from_ref: str | None = None
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_digest(self) -> ContaminationRecord:
        if self.record_digest != canonical_sha256(self.digest_payload()):
            raise ValueError("contamination record digest mismatch")
        return self

    def digest_payload(self) -> dict[str, str | None]:
        return {
            "memory_ref": self.memory_ref,
            "contamination_class": self.contamination_class.value,
            "evidence_digest": self.evidence_digest,
            "inherited_from_ref": self.inherited_from_ref,
        }


class MemoryContaminationRegistry:
    """Fail-closed marker surface for evaluator/holdout contamination.

    Marking only reduces trust. Existing descendants are recursively marked so a
    later-discovered contaminated ancestor cannot be consolidated as clean data.
    Materialized markers are committed to a chained manifest checkpoint so row
    mutation/deletion is detected before future formation work.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_contamination (
                    memory_ref TEXT NOT NULL,
                    contamination_class TEXT NOT NULL,
                    evidence_digest TEXT NOT NULL,
                    inherited_from_ref TEXT,
                    record_digest TEXT NOT NULL,
                    PRIMARY KEY(memory_ref, contamination_class)
                );
                CREATE TABLE IF NOT EXISTS memory_contamination_checkpoints (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    manifest_digest TEXT NOT NULL,
                    previous_checkpoint_hash TEXT NOT NULL,
                    checkpoint_hash TEXT NOT NULL
                );
                """
            )

    def mark(
        self,
        *,
        memory_ref: str,
        contamination_class: ContaminationClass,
        evidence_digest: str,
    ) -> tuple[ContaminationRecord, ...]:
        _parse_memory_ref(memory_ref)
        if len(evidence_digest) != 64:
            raise ValueError("evidence_digest must be sha256 hex")
        self.verify_integrity()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                inserted = self._insert_record(
                    connection,
                    memory_ref=memory_ref,
                    contamination_class=contamination_class,
                    evidence_digest=evidence_digest,
                    inherited_from_ref=None,
                )
                propagated = self._propagate_descendants(
                    connection,
                    roots={memory_ref},
                    contamination_class=contamination_class,
                    evidence_digest=evidence_digest,
                )
                if inserted is not None or propagated:
                    self._append_checkpoint(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        records = [inserted] if inserted is not None else []
        records.extend(propagated)
        return tuple(records)

    def verify_integrity(self) -> None:
        try:
            with closing(self._connect()) as connection:
                records = self._all_records(connection)
                manifest_digest = canonical_sha256(
                    [record.model_dump(mode="json") for record in records]
                )
                checkpoints = connection.execute(
                    """
                    SELECT manifest_digest, previous_checkpoint_hash, checkpoint_hash
                    FROM memory_contamination_checkpoints
                    ORDER BY sequence
                    """
                ).fetchall()
                previous = ""
                for row in checkpoints:
                    payload = {
                        "manifest_digest": row["manifest_digest"],
                        "previous_checkpoint_hash": row["previous_checkpoint_hash"],
                    }
                    if row["previous_checkpoint_hash"] != previous:
                        raise ValueError("contamination checkpoint chain mismatch")
                    if row["checkpoint_hash"] != canonical_sha256(payload):
                        raise ValueError("contamination checkpoint hash mismatch")
                    previous = row["checkpoint_hash"]
                if records and not checkpoints:
                    raise ValueError("contamination records lack a checkpoint")
                if checkpoints and checkpoints[-1]["manifest_digest"] != manifest_digest:
                    raise ValueError("contamination materialization/checkpoint mismatch")
        except MemoryContractError:
            raise
        except Exception as exc:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "Memory contamination integrity verification failed",
            ) from exc

    def records_for_refs(
        self,
        refs: tuple[str, ...],
    ) -> tuple[ContaminationRecord, ...]:
        if not refs:
            return ()
        self.verify_integrity()
        placeholders = ",".join("?" for _ in refs)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT memory_ref, contamination_class, evidence_digest,
                       inherited_from_ref, record_digest
                FROM memory_contamination
                WHERE memory_ref IN ({placeholders})
                ORDER BY memory_ref, contamination_class
                """,
                refs,
            ).fetchall()
        return tuple(ContaminationRecord(**dict(row)) for row in rows)

    def is_contaminated(self, memory_ref: str) -> bool:
        return bool(self.records_for_refs((memory_ref,)))

    def _propagate_descendants(
        self,
        connection: sqlite3.Connection,
        *,
        roots: set[str],
        contamination_class: ContaminationClass,
        evidence_digest: str,
    ) -> list[ContaminationRecord]:
        rows = connection.execute(
            "SELECT payload_json FROM revisions ORDER BY memory_id, revision_number"
        ).fetchall()
        revisions = [MemoryRevision.model_validate_json(row["payload_json"]) for row in rows]
        marked = set(roots)
        propagated: list[ContaminationRecord] = []
        changed = True
        while changed:
            changed = False
            for revision in revisions:
                if revision.ref in marked:
                    continue
                parents = set(revision.provenance.parent_memory_refs)
                source_parent = next((parent for parent in parents if parent in marked), None)
                if source_parent is None:
                    continue
                record = self._insert_record(
                    connection,
                    memory_ref=revision.ref,
                    contamination_class=contamination_class,
                    evidence_digest=evidence_digest,
                    inherited_from_ref=source_parent,
                )
                marked.add(revision.ref)
                changed = True
                if record is not None:
                    propagated.append(record)
        return propagated

    def _append_checkpoint(self, connection: sqlite3.Connection) -> None:
        records = self._all_records(connection)
        manifest_digest = canonical_sha256(
            [record.model_dump(mode="json") for record in records]
        )
        previous_row = connection.execute(
            """
            SELECT checkpoint_hash
            FROM memory_contamination_checkpoints
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()
        previous = "" if previous_row is None else previous_row["checkpoint_hash"]
        payload = {
            "manifest_digest": manifest_digest,
            "previous_checkpoint_hash": previous,
        }
        connection.execute(
            """
            INSERT INTO memory_contamination_checkpoints(
                manifest_digest, previous_checkpoint_hash, checkpoint_hash
            ) VALUES (?, ?, ?)
            """,
            (manifest_digest, previous, canonical_sha256(payload)),
        )

    @staticmethod
    def _all_records(connection: sqlite3.Connection) -> tuple[ContaminationRecord, ...]:
        rows = connection.execute(
            """
            SELECT memory_ref, contamination_class, evidence_digest,
                   inherited_from_ref, record_digest
            FROM memory_contamination
            ORDER BY memory_ref, contamination_class
            """
        ).fetchall()
        return tuple(ContaminationRecord(**dict(row)) for row in rows)

    @staticmethod
    def _insert_record(
        connection: sqlite3.Connection,
        *,
        memory_ref: str,
        contamination_class: ContaminationClass,
        evidence_digest: str,
        inherited_from_ref: str | None,
    ) -> ContaminationRecord | None:
        payload = {
            "memory_ref": memory_ref,
            "contamination_class": contamination_class.value,
            "evidence_digest": evidence_digest,
            "inherited_from_ref": inherited_from_ref,
        }
        record_digest = canonical_sha256(payload)
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO memory_contamination(
                memory_ref, contamination_class, evidence_digest,
                inherited_from_ref, record_digest
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                memory_ref,
                contamination_class.value,
                evidence_digest,
                inherited_from_ref,
                record_digest,
            ),
        )
        if cursor.rowcount != 1:
            return None
        return ContaminationRecord(**payload, record_digest=record_digest)


def _parse_memory_ref(ref: str) -> tuple[str, str]:
    memory_id, separator, revision_id = ref.partition("@")
    if (
        separator != "@"
        or not memory_id.startswith("mem_")
        or len(memory_id) != 36
        or not revision_id.startswith("rev_")
    ):
        raise ValueError("memory_ref must be exact memory_id@revision_id")
    return memory_id, revision_id
