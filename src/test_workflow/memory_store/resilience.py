from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..memory_contracts import ErrorCode, MemoryContractError, MemoryRevision, canonical_sha256
from .index import SQLiteDerivedIndex
from .retrieval import ProgressiveMemoryRetriever, RetrievalRequest, RetrievalResult


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IndexHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    CORRUPT = "CORRUPT"


class IndexHealthReport(FrozenModel):
    status: IndexHealthStatus
    primary_revision_count: int = Field(ge=0)
    indexed_revision_count: int = Field(ge=0)
    pending_outbox_count: int = Field(ge=0)
    missing_refs: tuple[str, ...] = ()
    orphan_refs: tuple[str, ...] = ()
    hash_mismatch_refs: tuple[str, ...] = ()
    forgotten_refs: tuple[str, ...] = ()
    invalid_source_sequence_refs: tuple[str, ...] = ()
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(
        cls,
        *,
        status: IndexHealthStatus,
        primary_revision_count: int,
        indexed_revision_count: int,
        pending_outbox_count: int,
        missing_refs: tuple[str, ...] = (),
        orphan_refs: tuple[str, ...] = (),
        hash_mismatch_refs: tuple[str, ...] = (),
        forgotten_refs: tuple[str, ...] = (),
        invalid_source_sequence_refs: tuple[str, ...] = (),
    ) -> IndexHealthReport:
        payload = {
            "status": status.value,
            "primary_revision_count": primary_revision_count,
            "indexed_revision_count": indexed_revision_count,
            "pending_outbox_count": pending_outbox_count,
            "missing_refs": missing_refs,
            "orphan_refs": orphan_refs,
            "hash_mismatch_refs": hash_mismatch_refs,
            "forgotten_refs": forgotten_refs,
            "invalid_source_sequence_refs": invalid_source_sequence_refs,
        }
        return cls(**payload, digest=canonical_sha256(payload))


class IndexRebuildReport(FrozenModel):
    before_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rebuilt_revision_count: int = Field(ge=0)
    source_outbox_high_watermark: int = Field(ge=0)
    primary_snapshot: str = Field(pattern=r"^[0-9a-f]{64}$")
    rebuild_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class RetrievalReplayEvidence(FrozenModel):
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: str
    stage: str
    released_refs: tuple[str, ...]
    released_hashes: tuple[str, ...]
    released_scores: tuple[float, ...]
    omitted_reasons: tuple[str, ...]
    primary_snapshot: str = Field(pattern=r"^[0-9a-f]{64}$")
    index_snapshot: str = Field(pattern=r"^[0-9a-f]{64}$")
    filter_version: str
    fusion_version: str
    result_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> RetrievalReplayEvidence:
        if self.manifest_digest != canonical_sha256(self.manifest_payload()):
            raise ValueError("retrieval replay evidence manifest is invalid")
        return self

    def manifest_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"manifest_digest"})

    @classmethod
    def capture(
        cls,
        *,
        request: RetrievalRequest,
        result: RetrievalResult,
    ) -> RetrievalReplayEvidence:
        payload = {
            "request_digest": request.request_digest,
            "status": result.status.value,
            "stage": result.stage_reached.value,
            "released_refs": tuple(item.ref for item in result.released),
            "released_hashes": tuple(item.content_hash for item in result.released),
            "released_scores": tuple(item.fusion_score for item in result.released),
            "omitted_reasons": result.omitted_reasons,
            "primary_snapshot": result.primary_snapshot,
            "index_snapshot": result.index_snapshot,
            "filter_version": result.filter_version,
            "fusion_version": result.fusion_version,
            "result_evidence_digest": result.evidence_digest,
        }
        return cls(**payload, manifest_digest=canonical_sha256(payload))


class ReplayVerification(FrozenModel):
    equivalent: bool
    expected_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed_result_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SQLiteIndexResilience:
    """Inspect and rebuild the replaceable SQLite derived index from primary truth."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.index = SQLiteDerivedIndex(self.db_path)
        self._initialize_rebuild_log()

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

    def _initialize_rebuild_log(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS index_rebuild_log (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    primary_snapshot TEXT NOT NULL,
                    outbox_high_watermark INTEGER NOT NULL,
                    rebuilt_revision_count INTEGER NOT NULL,
                    rebuild_digest TEXT NOT NULL
                )
                """
            )

    def inspect(self) -> IndexHealthReport:
        with closing(self._connect()) as connection:
            primary_rows = connection.execute(
                """
                SELECT memory_id, revision_id, payload_json
                FROM revisions
                ORDER BY memory_id, revision_id
                """
            ).fetchall()
            index_rows = connection.execute(
                """
                SELECT memory_id, revision_id, memory_ref, content_hash, source_sequence
                FROM search_index
                ORDER BY memory_ref
                """
            ).fetchall()
            forgotten_ids = {
                row["memory_id"]
                for row in connection.execute(
                    "SELECT memory_id FROM tombstones ORDER BY memory_id"
                )
            }
            pending = int(
                connection.execute(
                    "SELECT COUNT(*) FROM outbox WHERE applied = 0"
                ).fetchone()[0]
            )
            high_watermark = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) FROM outbox"
                ).fetchone()[0]
            )

        primary: dict[str, MemoryRevision] = {}
        for row in primary_rows:
            revision = MemoryRevision.model_validate_json(row["payload_json"])
            primary[revision.ref] = revision
        indexed = {row["memory_ref"]: row for row in index_rows}

        missing = tuple(sorted(set(primary) - set(indexed)))
        orphan = tuple(sorted(set(indexed) - set(primary)))
        mismatched = tuple(
            sorted(
                ref
                for ref in set(primary) & set(indexed)
                if indexed[ref]["content_hash"] != primary[ref].content_hash
            )
        )
        forgotten = tuple(
            sorted(
                row["memory_ref"]
                for row in index_rows
                if row["memory_id"] in forgotten_ids
            )
        )
        invalid_source = tuple(
            sorted(
                row["memory_ref"]
                for row in index_rows
                if int(row["source_sequence"]) < 1
                or int(row["source_sequence"]) > high_watermark
            )
        )

        if orphan or mismatched or forgotten or invalid_source:
            status = IndexHealthStatus.CORRUPT
        elif missing or pending:
            status = IndexHealthStatus.STALE
        else:
            status = IndexHealthStatus.HEALTHY
        return IndexHealthReport.create(
            status=status,
            primary_revision_count=len(primary),
            indexed_revision_count=len(indexed),
            pending_outbox_count=pending,
            missing_refs=missing,
            orphan_refs=orphan,
            hash_mismatch_refs=mismatched,
            forgotten_refs=forgotten,
            invalid_source_sequence_refs=invalid_source,
        )

    def rebuild(self) -> IndexRebuildReport:
        before = self.inspect()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                revision_rows = connection.execute(
                    """
                    SELECT payload_json
                    FROM revisions
                    ORDER BY memory_id, revision_number, revision_id
                    """
                ).fetchall()
                outbox_rows = connection.execute(
                    """
                    SELECT sequence, event_type, payload_json
                    FROM outbox
                    ORDER BY sequence
                    """
                ).fetchall()
                high_watermark = max(
                    (int(row["sequence"]) for row in outbox_rows),
                    default=0,
                )
                revision_sequences: dict[str, int] = {}
                for row in outbox_rows:
                    if row["event_type"] != "REVISION_COMMITTED":
                        continue
                    payload = json.loads(row["payload_json"])
                    revision_id = payload.get("revision_id")
                    if isinstance(revision_id, str):
                        revision_sequences[revision_id] = int(row["sequence"])

                connection.execute("DELETE FROM search_index")
                primary_snapshot_payload: list[dict[str, object]] = []
                rebuilt = 0
                for row in revision_rows:
                    revision = MemoryRevision.model_validate_json(row["payload_json"])
                    source_sequence = revision_sequences.get(revision.revision_id)
                    if source_sequence is None:
                        raise MemoryContractError(
                            ErrorCode.INTEGRITY_FAILED,
                            "primary revision is missing its authoritative outbox event",
                        )
                    connection.execute(
                        """
                        INSERT INTO search_index(
                            revision_id, memory_id, memory_ref, namespace,
                            memory_kind, schema_version, created_at,
                            content_hash, tokens_json, source_sequence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            revision.revision_id,
                            revision.memory_id,
                            revision.ref,
                            revision.namespace.canonical,
                            revision.memory_kind.value,
                            revision.schema_version,
                            revision.created_at.isoformat(),
                            revision.content_hash,
                            json.dumps(
                                SQLiteDerivedIndex._tokens(revision),
                                ensure_ascii=False,
                            ),
                            source_sequence,
                        ),
                    )
                    primary_snapshot_payload.append(
                        {
                            "ref": revision.ref,
                            "content_hash": revision.content_hash,
                            "source_sequence": source_sequence,
                        }
                    )
                    rebuilt += 1

                # This derived profile is now reconstructed through the current
                # authoritative outbox high-watermark. Future events remain pending.
                connection.execute(
                    "UPDATE outbox SET applied = 1 WHERE sequence <= ?",
                    (high_watermark,),
                )
                primary_snapshot = canonical_sha256(primary_snapshot_payload)
                rebuild_payload = {
                    "before_digest": before.digest,
                    "primary_snapshot": primary_snapshot,
                    "outbox_high_watermark": high_watermark,
                    "rebuilt_revision_count": rebuilt,
                }
                rebuild_digest = canonical_sha256(rebuild_payload)
                connection.execute(
                    """
                    INSERT INTO index_rebuild_log(
                        primary_snapshot, outbox_high_watermark,
                        rebuilt_revision_count, rebuild_digest
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        primary_snapshot,
                        high_watermark,
                        rebuilt,
                        rebuild_digest,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        after = self.inspect()
        if after.status is not IndexHealthStatus.HEALTHY:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "derived index rebuild did not converge to primary truth",
            )
        return IndexRebuildReport(
            before_digest=before.digest,
            after_digest=after.digest,
            rebuilt_revision_count=rebuilt,
            source_outbox_high_watermark=high_watermark,
            primary_snapshot=primary_snapshot,
            rebuild_digest=rebuild_digest,
        )


class RetrievalReplayVerifier:
    """Independent deterministic replay verifier using digest-only evidence."""

    def __init__(self, retriever: ProgressiveMemoryRetriever) -> None:
        self.retriever = retriever

    @staticmethod
    def capture(
        *,
        request: RetrievalRequest,
        result: RetrievalResult,
    ) -> RetrievalReplayEvidence:
        return RetrievalReplayEvidence.capture(request=request, result=result)

    def verify(
        self,
        *,
        request: RetrievalRequest,
        evidence: RetrievalReplayEvidence,
    ) -> ReplayVerification:
        if request.request_digest != evidence.request_digest:
            raise MemoryContractError(
                ErrorCode.INTEGRITY_FAILED,
                "replay request does not match captured request digest",
            )
        replayed = self.retriever.retrieve(request)
        actual = RetrievalReplayEvidence.capture(request=request, result=replayed)
        return ReplayVerification(
            equivalent=actual.manifest_digest == evidence.manifest_digest,
            expected_manifest_digest=evidence.manifest_digest,
            actual_manifest_digest=actual.manifest_digest,
            replayed_result_evidence_digest=replayed.evidence_digest,
        )
