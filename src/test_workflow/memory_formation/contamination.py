from __future__ import annotations

import sqlite3
from contextlib import closing
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..memory_contracts import MemoryRevision, canonical_sha256


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


class MemoryContaminationRegistry:
    """Fail-closed marker surface for evaluator/holdout contamination.

    Marking only reduces trust. Existing descendants are recursively marked so a
    later-discovered contaminated ancestor cannot be consolidated as clean data.
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_contamination (
                    memory_ref TEXT NOT NULL,
                    contamination_class TEXT NOT NULL,
                    evidence_digest TEXT NOT NULL,
                    inherited_from_ref TEXT,
                    record_digest TEXT NOT NULL,
                    PRIMARY KEY(memory_ref, contamination_class)
                )
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
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        records = [inserted] if inserted is not None else []
        records.extend(propagated)
        return tuple(records)

    def records_for_refs(
        self,
        refs: tuple[str, ...],
    ) -> tuple[ContaminationRecord, ...]:
        if not refs:
            return ()
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
