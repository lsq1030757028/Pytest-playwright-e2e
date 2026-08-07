from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..memory_contracts import MemoryRevision, canonical_sha256
from .resilience import IndexRebuildReport, SQLiteIndexResilience
from .retrieval import (
    BudgetConsumption,
    ProgressiveMemoryRetriever,
    RetrievalRequest,
    RetrievalResult,
    RetrievalStage,
    RetrievalStatus,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OutboxHealthReport(FrozenModel):
    unreconciled_sequence_gaps: tuple[int, ...]
    missing_revision_event_refs: tuple[str, ...]
    high_watermark: int = Field(ge=0)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def healthy(self) -> bool:
        return not self.unreconciled_sequence_gaps and not self.missing_revision_event_refs


class OutboxRecoveryReport(FrozenModel):
    before_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reconciled_sequence_gaps: tuple[int, ...]
    recreated_revision_events: tuple[str, ...]
    index_rebuild: IndexRebuildReport
    recovery_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SQLiteOutboxRecovery:
    """Detect missing outbox history and reconcile it from primary truth.

    Historical sequence numbers are never rewritten. A missing Revision event is
    represented by a new append-only reconciliation event, while deleted numeric
    sequence slots are recorded as reconciled gaps for audit/replay evidence.
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
                CREATE TABLE IF NOT EXISTS outbox_gap_reconciliation (
                    missing_sequence INTEGER PRIMARY KEY,
                    reconciled_by_event_id TEXT NOT NULL,
                    evidence_digest TEXT NOT NULL
                )
                """
            )

    def inspect(self) -> OutboxHealthReport:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_type, payload_json
                FROM outbox
                ORDER BY sequence
                """
            ).fetchall()
            reconciled_gaps = {
                int(row[0])
                for row in connection.execute(
                    "SELECT missing_sequence FROM outbox_gap_reconciliation"
                )
            }
            revision_rows = connection.execute(
                "SELECT payload_json FROM revisions ORDER BY revision_id"
            ).fetchall()

        sequences = [int(row["sequence"]) for row in rows]
        high = max(sequences, default=0)
        present = set(sequences)
        raw_gaps = {
            sequence
            for sequence in range(1, high + 1)
            if sequence not in present
        }
        gaps = tuple(sorted(raw_gaps - reconciled_gaps))

        revision_event_ids: set[str] = set()
        for row in rows:
            if row["event_type"] not in {"REVISION_COMMITTED", "REVISION_RECONCILED"}:
                continue
            payload = json.loads(row["payload_json"])
            revision_id = payload.get("revision_id")
            if isinstance(revision_id, str):
                revision_event_ids.add(revision_id)
        missing_refs: list[str] = []
        for row in revision_rows:
            revision = MemoryRevision.model_validate_json(row["payload_json"])
            if revision.revision_id not in revision_event_ids:
                missing_refs.append(revision.ref)

        payload = {
            "unreconciled_sequence_gaps": gaps,
            "missing_revision_event_refs": tuple(sorted(missing_refs)),
            "high_watermark": high,
        }
        return OutboxHealthReport(**payload, digest=canonical_sha256(payload))

    def recover(self) -> OutboxRecoveryReport:
        before = self.inspect()
        recreated_refs: list[str] = []
        reconciled_gaps = before.unreconciled_sequence_gaps
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                revision_rows = connection.execute(
                    "SELECT payload_json FROM revisions ORDER BY revision_id"
                ).fetchall()
                event_rows = connection.execute(
                    """
                    SELECT event_type, payload_json
                    FROM outbox
                    WHERE event_type IN ('REVISION_COMMITTED', 'REVISION_RECONCILED')
                    """
                ).fetchall()
                event_revision_ids: set[str] = set()
                for row in event_rows:
                    payload = json.loads(row["payload_json"])
                    revision_id = payload.get("revision_id")
                    if isinstance(revision_id, str):
                        event_revision_ids.add(revision_id)

                reconciliation_event_ids: list[str] = []
                for row in revision_rows:
                    revision = MemoryRevision.model_validate_json(row["payload_json"])
                    if revision.revision_id in event_revision_ids:
                        continue
                    payload = {
                        "memory_id": revision.memory_id,
                        "revision_id": revision.revision_id,
                        "revision_number": revision.revision_number,
                        "content_hash": revision.content_hash,
                        "reconciliation": True,
                    }
                    event_id = "outbox_reconciled_" + canonical_sha256(
                        {
                            "revision_id": revision.revision_id,
                            "content_hash": revision.content_hash,
                        }
                    )
                    connection.execute(
                        """
                        INSERT INTO outbox(
                            event_id, event_type, memory_id, namespace,
                            payload_json, created_at, applied
                        ) VALUES (?, 'REVISION_RECONCILED', ?, ?, ?, ?, 0)
                        """,
                        (
                            event_id,
                            revision.memory_id,
                            revision.namespace.canonical,
                            json.dumps(payload, ensure_ascii=False, sort_keys=True),
                            revision.created_at.isoformat(),
                        ),
                    )
                    recreated_refs.append(revision.ref)
                    reconciliation_event_ids.append(event_id)

                evidence_seed = {
                    "before_digest": before.digest,
                    "gaps": reconciled_gaps,
                    "recreated_refs": tuple(recreated_refs),
                    "events": tuple(reconciliation_event_ids),
                }
                evidence_digest = canonical_sha256(evidence_seed)
                evidence_event = (
                    reconciliation_event_ids[-1]
                    if reconciliation_event_ids
                    else "outbox_gap_" + evidence_digest
                )
                for sequence in reconciled_gaps:
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO outbox_gap_reconciliation(
                            missing_sequence, reconciled_by_event_id, evidence_digest
                        ) VALUES (?, ?, ?)
                        """,
                        (sequence, evidence_event, evidence_digest),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        # Rebuild consumes the reconciled stream and proves derived convergence.
        index_rebuild = SQLiteIndexResilience(self.db_path).rebuild()
        after = self.inspect()
        if not after.healthy:
            raise RuntimeError("outbox recovery did not converge")
        recovery_payload = {
            "before_digest": before.digest,
            "after_digest": after.digest,
            "reconciled_sequence_gaps": reconciled_gaps,
            "recreated_revision_events": tuple(recreated_refs),
            "index_rebuild_digest": index_rebuild.rebuild_digest,
        }
        return OutboxRecoveryReport(
            before_digest=before.digest,
            after_digest=after.digest,
            reconciled_sequence_gaps=reconciled_gaps,
            recreated_revision_events=tuple(recreated_refs),
            index_rebuild=index_rebuild,
            recovery_digest=canonical_sha256(recovery_payload),
        )


class FailClosedRetrievalGateway:
    """Convert primary storage/integrity outages into metadata-free BLOCKED results."""

    def __init__(self, retriever: ProgressiveMemoryRetriever) -> None:
        self.retriever = retriever

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        try:
            return self.retriever.retrieve(request)
        except sqlite3.Error:
            return self._blocked(request, "PRIMARY_STORE_UNAVAILABLE")
        except Exception as exc:
            # Integrity/epoch uncertainty must never widen content release.
            if getattr(exc, "code", None) is not None:
                return self._blocked(request, "PRIMARY_AUTHORITY_UNKNOWN")
            raise

    @staticmethod
    def _blocked(request: RetrievalRequest, reason: str) -> RetrievalResult:
        primary_snapshot = canonical_sha256({"primary": "unavailable"})
        index_snapshot = canonical_sha256({"index": "not_authoritative"})
        evidence = canonical_sha256(
            {
                "request": request.request_digest,
                "status": RetrievalStatus.BLOCKED.value,
                "stage": RetrievalStage.HOT.value,
                "reason": reason,
                "primary_snapshot": primary_snapshot,
                "index_snapshot": index_snapshot,
            }
        )
        return RetrievalResult(
            status=RetrievalStatus.BLOCKED,
            stage_reached=RetrievalStage.HOT,
            released=(),
            omitted_reasons=(reason,),
            budget=BudgetConsumption(
                authorized_candidates=0,
                released=0,
                estimated_tokens=0,
                elapsed_ms=0,
            ),
            primary_snapshot=primary_snapshot,
            index_snapshot=index_snapshot,
            evidence_digest=evidence,
        )
