from __future__ import annotations

import json
import math
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..memory_contracts import (
    AccessOperation,
    AclEntry,
    CreatorType,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    PrincipalContext,
    PrincipalType,
    Provenance,
    RetentionPolicy,
    StateEvent,
    TransformationKind,
    canonical_sha256,
)
from ..memory_contracts.policy import evaluate_permission
from ..memory_store import SQLiteMemoryStore

_MAX_PARENT_REFS = 128
_MAX_TOKENS = 16_000
_MAX_WALL_MS = 10_000
_MAX_DERIVATION_DEPTH = 2
_ACTIVE_PARENT_STATES = frozenset(
    {LifecycleState.CANDIDATE, LifecycleState.VERIFIED, LifecycleState.PROMOTED}
)
_PROTECTED_AUTHORITY_KEYS = frozenset(
    {
        "oracle_override",
        "policy_override",
        "permission_override",
        "lifecycle_override",
        "assurance_override",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConsolidationStatus(StrEnum):
    CREATED_CANDIDATE = "CREATED_CANDIDATE"
    APPENDED_CANDIDATE_REVISION = "APPENDED_CANDIDATE_REVISION"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    CONFLICT_REQUIRES_REVIEW = "CONFLICT_REQUIRES_REVIEW"
    REJECTED = "REJECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ParentSnapshot(FrozenModel):
    ref: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: LifecycleState
    memory_kind: MemoryKind
    derivation_depth: int = Field(ge=0, le=_MAX_DERIVATION_DEPTH)


class ConsolidationBudgetConsumption(FrozenModel):
    parent_count: int = Field(ge=0, le=_MAX_PARENT_REFS)
    estimated_tokens: int = Field(ge=0)
    output_count: int = Field(ge=0, le=1)
    derivation_depth: int = Field(ge=0)
    elapsed_ms_before_store: int = Field(ge=0)


class ConsolidationRequest(FrozenModel):
    request_id: str = Field(min_length=1, max_length=255)
    actor: PrincipalContext
    target_namespace: MemoryNamespace
    parent_memory_refs: tuple[str, ...] = Field(min_length=1, max_length=_MAX_PARENT_REFS)
    memory_kind: MemoryKind
    candidate_content: dict[str, Any]
    authority_refs: tuple[str, ...] = Field(min_length=1)
    formation_rule_ref: str = Field(
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$"
    )
    validator_profile_ref: str = Field(
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$"
    )
    retention_policy: RetentionPolicy
    semantic_subject_key: str | None = Field(default=None, min_length=1, max_length=255)
    expected_head_revision_id: str | None = None
    idempotency_key: str = Field(
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,254}$"
    )
    now: datetime

    @model_validator(mode="after")
    def validate_request(self) -> ConsolidationRequest:
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if len(set(self.parent_memory_refs)) != len(self.parent_memory_refs):
            raise ValueError("duplicate parent Memory refs are not allowed")
        for ref in self.parent_memory_refs:
            _parse_memory_ref(ref)
        if self.memory_kind not in {MemoryKind.SEMANTIC, MemoryKind.EPISODIC}:
            raise ValueError("I2 consolidation supports Semantic or Episodic output only")
        if not self.candidate_content:
            raise ValueError("candidate_content must not be empty")
        if self.memory_kind is MemoryKind.SEMANTIC:
            claim = self.candidate_content.get("claim")
            if not isinstance(claim, str) or not claim.strip():
                raise ValueError("semantic consolidation requires a non-empty claim")
        return self

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


class ConsolidationEvent(FrozenModel):
    event_id: str = Field(pattern=r"^consolidation_[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposed_memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor_principal_ref: str
    target_namespace: str
    occurred_at: datetime
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> ConsolidationEvent:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("consolidation event time must be timezone-aware")
        if self.event_hash != canonical_sha256(self.hash_payload()):
            raise ValueError("consolidation event hash mismatch")
        return self

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"event_hash"})

    @classmethod
    def create(
        cls,
        *,
        request: ConsolidationRequest,
        proposed_memory_id: str,
        proposal_digest: str,
    ) -> ConsolidationEvent:
        seed = {
            "request_digest": request.request_digest,
            "proposed_memory_id": proposed_memory_id,
            "proposal_digest": proposal_digest,
            "actor": request.actor.principal_id,
            "target_namespace": request.target_namespace.canonical,
            "occurred_at": request.now,
        }
        payload = {
            "event_id": f"consolidation_{canonical_sha256(seed)}",
            "request_digest": request.request_digest,
            "proposed_memory_id": proposed_memory_id,
            "proposal_digest": proposal_digest,
            "actor_principal_ref": request.actor.principal_id,
            "target_namespace": request.target_namespace.canonical,
            "occurred_at": request.now,
        }
        return cls(**payload, event_hash=canonical_sha256(payload))


class ConsolidationReplayEvidence(FrozenModel):
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_snapshots: tuple[ParentSnapshot, ...]
    parent_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    validator_profile_ref: str
    status: ConsolidationStatus
    candidate_revision_ref: str | None = None
    candidate_content_hash: str | None = None
    store_audit_ref: str | None = None
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> ConsolidationReplayEvidence:
        snapshots = [item.model_dump(mode="json") for item in self.parent_snapshots]
        if self.parent_snapshot_digest != canonical_sha256(snapshots):
            raise ValueError("parent snapshot digest mismatch")
        if self.manifest_digest != canonical_sha256(
            self.model_dump(mode="json", exclude={"manifest_digest"})
        ):
            raise ValueError("consolidation replay manifest mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        request_digest: str,
        event_hash: str,
        parent_snapshots: tuple[ParentSnapshot, ...],
        proposal_digest: str,
        validator_profile_ref: str,
        status: ConsolidationStatus,
        candidate_revision_ref: str | None,
        candidate_content_hash: str | None,
        store_audit_ref: str | None,
    ) -> ConsolidationReplayEvidence:
        snapshots = [item.model_dump(mode="json") for item in parent_snapshots]
        payload = {
            "request_digest": request_digest,
            "event_hash": event_hash,
            "parent_snapshots": snapshots,
            "parent_snapshot_digest": canonical_sha256(snapshots),
            "proposal_digest": proposal_digest,
            "validator_profile_ref": validator_profile_ref,
            "status": status.value,
            "candidate_revision_ref": candidate_revision_ref,
            "candidate_content_hash": candidate_content_hash,
            "store_audit_ref": store_audit_ref,
        }
        return cls(**payload, manifest_digest=canonical_sha256(payload))


class ConsolidationResult(FrozenModel):
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    consolidation_event_ref: str
    status: ConsolidationStatus
    candidate_revision_ref: str | None = None
    candidate_content_hash: str | None = None
    effective_lifecycle: LifecycleState | None = None
    parent_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate_ref: str | None = None
    conflict_refs: tuple[str, ...] = ()
    rejected_reasons: tuple[str, ...] = ()
    budget: ConsolidationBudgetConsumption
    store_audit_ref: str | None = None
    replay_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ConsolidationAdmissionError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _ParentRecord(FrozenModel):
    snapshot: ParentSnapshot
    revision: MemoryRevision


class BackgroundConsolidator:
    """M1C-I2 deterministic reference consolidator."""

    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.store = store
        self.db_path = Path(store.db_path)
        self._initialize_tables()

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

    def _initialize_tables(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS consolidation_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    request_fingerprint TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('IN_PROGRESS', 'DONE')),
                    result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS consolidation_events (
                    event_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consolidation_replay (
                    request_digest TEXT PRIMARY KEY,
                    manifest_digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def consolidate(self, request: ConsolidationRequest) -> ConsolidationResult:
        started = time.perf_counter()
        proposal_digest = self._proposal_digest(request)
        memory_id = self._memory_id(request)
        event = ConsolidationEvent.create(
            request=request,
            proposed_memory_id=memory_id,
            proposal_digest=proposal_digest,
        )
        if not self._target_authorized(request):
            return self._ephemeral_rejection(
                request, event, proposal_digest, started, "TARGET_NAMESPACE_AUTHORITY_DENIED"
            )

        fingerprint = canonical_sha256(
            {
                "actor_principal_id": request.actor.principal_id,
                "request_digest": request.request_digest,
            }
        )
        reservation = self._reserve(request, fingerprint)
        if isinstance(reservation, ConsolidationResult):
            return reservation
        if reservation == "REBOUND":
            return self._ephemeral_rejection(
                request, event, proposal_digest, started, "IDEMPOTENCY_KEY_REBOUND"
            )

        try:
            parents = self._admit_parents(request)
            self._validate_candidate(request, parents)
        except ConsolidationAdmissionError as exc:
            status = (
                ConsolidationStatus.BUDGET_EXHAUSTED
                if "BUDGET" in exc.reason or "DEPTH" in exc.reason
                else ConsolidationStatus.REJECTED
            )
            return self._finish(
                request=request,
                fingerprint=fingerprint,
                event=event,
                status=status,
                proposal_digest=proposal_digest,
                parents=(),
                started=started,
                rejected_reasons=(exc.reason,),
            )

        estimated_tokens = self._estimate_tokens(request, parents)
        derivation_depth = 1 + max(item.snapshot.derivation_depth for item in parents)
        if estimated_tokens > _MAX_TOKENS:
            return self._budget_failure(
                request,
                fingerprint,
                event,
                proposal_digest,
                parents,
                started,
                estimated_tokens,
                derivation_depth,
                "BACKGROUND_TOKEN_BUDGET_EXHAUSTED",
            )
        if derivation_depth > _MAX_DERIVATION_DEPTH:
            return self._budget_failure(
                request,
                fingerprint,
                event,
                proposal_digest,
                parents,
                started,
                estimated_tokens,
                derivation_depth,
                "BACKGROUND_DERIVATION_DEPTH_EXHAUSTED",
            )
        if int((time.perf_counter() - started) * 1000) > _MAX_WALL_MS:
            return self._budget_failure(
                request,
                fingerprint,
                event,
                proposal_digest,
                parents,
                started,
                estimated_tokens,
                derivation_depth,
                "BACKGROUND_LATENCY_BUDGET_EXHAUSTED",
            )
        if not self._revalidate(request, parents):
            return self._finish(
                request=request,
                fingerprint=fingerprint,
                event=event,
                status=ConsolidationStatus.REJECTED,
                proposal_digest=proposal_digest,
                parents=parents,
                started=started,
                estimated_tokens=estimated_tokens,
                derivation_depth=derivation_depth,
                rejected_reasons=("PARENT_SNAPSHOT_CHANGED",),
            )

        try:
            existing, existing_state = self._existing_target(request, memory_id)
        except ConsolidationAdmissionError as exc:
            return self._finish(
                request=request,
                fingerprint=fingerprint,
                event=event,
                status=ConsolidationStatus.REJECTED,
                proposal_digest=proposal_digest,
                parents=parents,
                started=started,
                estimated_tokens=estimated_tokens,
                derivation_depth=derivation_depth,
                rejected_reasons=(exc.reason,),
            )

        if existing is not None:
            duplicate = self._logical_digest(existing) == proposal_digest
            if duplicate and existing_state is LifecycleState.CANDIDATE:
                return self._finish(
                    request=request,
                    fingerprint=fingerprint,
                    event=event,
                    status=ConsolidationStatus.DUPLICATE_SUPPRESSED,
                    proposal_digest=proposal_digest,
                    parents=parents,
                    started=started,
                    estimated_tokens=estimated_tokens,
                    derivation_depth=derivation_depth,
                    candidate_revision_ref=existing.ref,
                    candidate_content_hash=existing.content_hash,
                    effective_lifecycle=existing_state,
                    duplicate_ref=existing.ref,
                )
            if request.expected_head_revision_id != existing.revision_id:
                reason = (
                    "EXISTING_AUTHORITY_NOT_CANDIDATE"
                    if duplicate
                    else "SEMANTIC_SUBJECT_CONFLICT"
                )
                return self._finish(
                    request=request,
                    fingerprint=fingerprint,
                    event=event,
                    status=ConsolidationStatus.CONFLICT_REQUIRES_REVIEW,
                    proposal_digest=proposal_digest,
                    parents=parents,
                    started=started,
                    estimated_tokens=estimated_tokens,
                    derivation_depth=derivation_depth,
                    conflict_refs=(existing.ref,),
                    rejected_reasons=(reason,),
                )
        elif request.expected_head_revision_id is not None:
            return self._finish(
                request=request,
                fingerprint=fingerprint,
                event=event,
                status=ConsolidationStatus.CONFLICT_REQUIRES_REVIEW,
                proposal_digest=proposal_digest,
                parents=parents,
                started=started,
                estimated_tokens=estimated_tokens,
                derivation_depth=derivation_depth,
                rejected_reasons=("EXPECTED_HEAD_NOT_FOUND",),
            )

        revision = self._build_revision(request, event, parents, memory_id, existing)
        parent_refs = tuple(item.snapshot.ref for item in parents)
        resolved_sources = {
            item.snapshot.ref: item.snapshot.content_hash for item in parents
        }
        request_store = SQLiteMemoryStore(
            self.db_path,
            resolved_sources=resolved_sources,
            resolved_evidence=parent_refs,
        )
        store_result = request_store.append_revision(
            actor=request.actor,
            revision=revision,
            expected_head_revision_id=(
                existing.revision_id if existing is not None else None
            ),
            correlation_id=f"consolidation/{request.request_id}",
        )
        if store_result.decision is Decision.ACCEPTED:
            lifecycle = request_store.get_effective_state(memory_id=revision.memory_id)
            if lifecycle is not LifecycleState.CANDIDATE:
                raise MemoryContractError(
                    ErrorCode.INTEGRITY_FAILED,
                    "M1C consolidation produced a non-Candidate lifecycle",
                )
            status = (
                ConsolidationStatus.CREATED_CANDIDATE
                if existing is None
                else ConsolidationStatus.APPENDED_CANDIDATE_REVISION
            )
            return self._finish(
                request=request,
                fingerprint=fingerprint,
                event=event,
                status=status,
                proposal_digest=proposal_digest,
                parents=parents,
                started=started,
                estimated_tokens=estimated_tokens,
                derivation_depth=derivation_depth,
                candidate_revision_ref=revision.ref,
                candidate_content_hash=revision.content_hash,
                effective_lifecycle=lifecycle,
                store_audit_ref=store_result.audit_event_ref,
            )
        if store_result.decision is Decision.CONFLICT:
            return self._finish(
                request=request,
                fingerprint=fingerprint,
                event=event,
                status=ConsolidationStatus.CONFLICT_REQUIRES_REVIEW,
                proposal_digest=proposal_digest,
                parents=parents,
                started=started,
                estimated_tokens=estimated_tokens,
                derivation_depth=derivation_depth,
                rejected_reasons=("STORE_CAS_CONFLICT",),
            )
        reason = (
            store_result.error_code.value
            if store_result.error_code is not None
            else "STORE_REJECTED"
        )
        return self._finish(
            request=request,
            fingerprint=fingerprint,
            event=event,
            status=ConsolidationStatus.REJECTED,
            proposal_digest=proposal_digest,
            parents=parents,
            started=started,
            estimated_tokens=estimated_tokens,
            derivation_depth=derivation_depth,
            rejected_reasons=(reason,),
        )

    def replay_evidence(self, request_digest: str) -> ConsolidationReplayEvidence:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload_json FROM consolidation_replay WHERE request_digest = ?",
                (request_digest,),
            ).fetchone()
        if row is None:
            raise KeyError(request_digest)
        return ConsolidationReplayEvidence.model_validate_json(row["payload_json"])

    def _target_authorized(self, request: ConsolidationRequest) -> bool:
        with closing(self._connect()) as connection:
            entries = self._acl_entries(connection, request.target_namespace.canonical)
        return all(
            evaluate_permission(
                actor=request.actor,
                namespace=request.target_namespace,
                operation=operation,
                acl_entries=entries,
            ).allowed
            for operation in (
                AccessOperation.APPEND_REVISION,
                AccessOperation.QUERY,
                AccessOperation.READ_CONTENT,
            )
        )

    @staticmethod
    def _acl_entries(
        connection: sqlite3.Connection,
        namespace: str,
    ) -> tuple[AclEntry, ...]:
        rows = connection.execute(
            """
            SELECT payload_json FROM acl_events
            WHERE namespace = ? ORDER BY sequence
            """,
            (namespace,),
        ).fetchall()
        return tuple(AclEntry.model_validate_json(row["payload_json"]) for row in rows)

    def _admit_parents(
        self,
        request: ConsolidationRequest,
    ) -> tuple[_ParentRecord, ...]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            try:
                metadata: list[tuple[str, str, LifecycleState]] = []
                for ref in request.parent_memory_refs:
                    memory_id, revision_id = _parse_memory_ref(ref)
                    row = connection.execute(
                        """
                        SELECT r.namespace, h.revision_id AS head_revision_id
                        FROM revisions AS r
                        LEFT JOIN heads AS h ON h.memory_id = r.memory_id
                        WHERE r.memory_id = ? AND r.revision_id = ?
                        """,
                        (memory_id, revision_id),
                    ).fetchone()
                    if row is None or row["namespace"] != request.target_namespace.canonical:
                        raise ConsolidationAdmissionError("PARENT_NOT_ADMISSIBLE")
                    if row["head_revision_id"] != revision_id:
                        raise ConsolidationAdmissionError("PARENT_NOT_CURRENT_HEAD")
                    state = self._current_state(connection, memory_id)
                    if state not in _ACTIVE_PARENT_STATES:
                        raise ConsolidationAdmissionError("PARENT_STATE_NOT_CONSOLIDATABLE")
                    metadata.append((ref, revision_id, state))

                records: list[_ParentRecord] = []
                for ref, revision_id, state in metadata:
                    row = connection.execute(
                        "SELECT payload_json FROM revisions WHERE revision_id = ?",
                        (revision_id,),
                    ).fetchone()
                    if row is None:
                        raise ConsolidationAdmissionError("PARENT_SNAPSHOT_CHANGED")
                    revision = MemoryRevision.model_validate_json(row["payload_json"])
                    if revision.memory_kind not in {
                        MemoryKind.SEMANTIC,
                        MemoryKind.EPISODIC,
                    }:
                        raise ConsolidationAdmissionError("PARENT_KIND_NOT_CONSOLIDATABLE")
                    depth = self._revision_depth(
                        connection,
                        request=request,
                        revision=revision,
                        visited={ref},
                    )
                    records.append(
                        _ParentRecord(
                            snapshot=ParentSnapshot(
                                ref=ref,
                                content_hash=revision.content_hash,
                                lifecycle=state,
                                memory_kind=revision.memory_kind,
                                derivation_depth=depth,
                            ),
                            revision=revision,
                        )
                    )
                connection.commit()
                return tuple(records)
            except Exception:
                connection.rollback()
                raise

    def _revision_depth(
        self,
        connection: sqlite3.Connection,
        *,
        request: ConsolidationRequest,
        revision: MemoryRevision,
        visited: set[str],
    ) -> int:
        if not revision.formation_event_ref.startswith("consolidation_"):
            return 0
        parent_refs = tuple(revision.provenance.parent_memory_refs)
        if not parent_refs:
            return 1
        depths: list[int] = []
        for ref in parent_refs:
            if ref in visited:
                raise ConsolidationAdmissionError("CONSOLIDATION_PARENT_CYCLE")
            memory_id, revision_id = _parse_memory_ref(ref)
            row = connection.execute(
                """
                SELECT r.namespace, r.payload_json, h.revision_id AS head_revision_id
                FROM revisions AS r
                LEFT JOIN heads AS h ON h.memory_id = r.memory_id
                WHERE r.memory_id = ? AND r.revision_id = ?
                """,
                (memory_id, revision_id),
            ).fetchone()
            if (
                row is None
                or row["namespace"] != request.target_namespace.canonical
                or row["head_revision_id"] != revision_id
            ):
                raise ConsolidationAdmissionError("ANCESTOR_NOT_ADMISSIBLE")
            if self._current_state(connection, memory_id) not in _ACTIVE_PARENT_STATES:
                raise ConsolidationAdmissionError("ANCESTOR_STATE_NOT_CONSOLIDATABLE")
            ancestor = MemoryRevision.model_validate_json(row["payload_json"])
            depths.append(
                self._revision_depth(
                    connection,
                    request=request,
                    revision=ancestor,
                    visited=visited | {ref},
                )
            )
        return 1 + max(depths, default=0)

    @staticmethod
    def _current_state(
        connection: sqlite3.Connection,
        memory_id: str,
    ) -> LifecycleState:
        if connection.execute(
            "SELECT 1 FROM tombstones WHERE memory_id = ?",
            (memory_id,),
        ).fetchone():
            return LifecycleState.FORGOTTEN
        head = connection.execute(
            "SELECT revision_id FROM heads WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if head is None:
            return LifecycleState.CANDIDATE
        row = connection.execute(
            """
            SELECT payload_json FROM state_events
            WHERE memory_id = ? AND revision_id = ?
            ORDER BY sequence DESC LIMIT 1
            """,
            (memory_id, head["revision_id"]),
        ).fetchone()
        return (
            LifecycleState.CANDIDATE
            if row is None
            else StateEvent.model_validate_json(row["payload_json"]).to_state
        )

    def _validate_candidate(
        self,
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> None:
        if _find_keys(request.candidate_content) & _PROTECTED_AUTHORITY_KEYS:
            raise ConsolidationAdmissionError("PROTECTED_AUTHORITY_MUTATION_ATTEMPT")
        if request.memory_kind is MemoryKind.SEMANTIC:
            claim = request.candidate_content["claim"]
            supported = any(
                claim
                in json.dumps(
                    item.revision.content,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                for item in parents
            )
            if not supported:
                raise ConsolidationAdmissionError("UNSUPPORTED_CONSOLIDATED_CLAIM")

    @staticmethod
    def _estimate_tokens(
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> int:
        characters = len(
            json.dumps(request.candidate_content, ensure_ascii=False, sort_keys=True)
        ) + sum(
            len(json.dumps(item.revision.content, ensure_ascii=False, sort_keys=True))
            for item in parents
        )
        return max(1, math.ceil(characters / 4))

    def _revalidate(
        self,
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> bool:
        if not self._target_authorized(request):
            return False
        with closing(self._connect()) as connection:
            for item in parents:
                memory_id, revision_id = _parse_memory_ref(item.snapshot.ref)
                row = connection.execute(
                    """
                    SELECT r.payload_json, h.revision_id AS head_revision_id
                    FROM revisions AS r
                    LEFT JOIN heads AS h ON h.memory_id = r.memory_id
                    WHERE r.memory_id = ? AND r.revision_id = ?
                    """,
                    (memory_id, revision_id),
                ).fetchone()
                if row is None or row["head_revision_id"] != revision_id:
                    return False
                state = self._current_state(connection, memory_id)
                if state != item.snapshot.lifecycle or state not in _ACTIVE_PARENT_STATES:
                    return False
                revision = MemoryRevision.model_validate_json(row["payload_json"])
                if revision.content_hash != item.snapshot.content_hash:
                    return False
        return True

    def _existing_target(
        self,
        request: ConsolidationRequest,
        memory_id: str,
    ) -> tuple[MemoryRevision | None, LifecycleState | None]:
        with closing(self._connect()) as connection:
            if connection.execute(
                "SELECT 1 FROM tombstones WHERE memory_id = ?",
                (memory_id,),
            ).fetchone():
                raise ConsolidationAdmissionError("FORGOTTEN_SUBJECT_CANNOT_RESURRECT")
            row = connection.execute(
                """
                SELECT r.payload_json FROM heads AS h
                JOIN revisions AS r ON r.revision_id = h.revision_id
                WHERE h.memory_id = ?
                """,
                (memory_id,),
            ).fetchone()
            if row is None:
                return None, None
            revision = MemoryRevision.model_validate_json(row["payload_json"])
            return revision, self._current_state(connection, memory_id)

    def _build_revision(
        self,
        request: ConsolidationRequest,
        event: ConsolidationEvent,
        parents: tuple[_ParentRecord, ...],
        memory_id: str,
        existing: MemoryRevision | None,
    ) -> MemoryRevision:
        parent_refs = tuple(item.snapshot.ref for item in parents)
        provenance = Provenance(
            source_refs=parent_refs,
            evidence_refs=parent_refs,
            source_content_hashes={
                item.snapshot.ref: item.snapshot.content_hash for item in parents
            },
            created_by_principal=request.actor.principal_id,
            creator_type=_creator_type(request.actor.principal_type),
            capability_or_formation_rule_ref=request.formation_rule_ref,
            requirement_revision_refs=tuple(
                ref for ref in request.authority_refs if ref.startswith("requirement/")
            ),
            code_revision_refs=tuple(
                ref for ref in request.authority_refs if ref.startswith("code/")
            ),
            environment_revision_refs=tuple(
                ref for ref in request.authority_refs if ref.startswith("environment/")
            ),
            parent_memory_refs=parent_refs,
            transformation_kind=TransformationKind.SUMMARY,
        )
        revision_number = 1 if existing is None else existing.revision_number + 1
        revision_nonce = canonical_sha256(
            {
                "request_digest": request.request_digest,
                "memory_id": memory_id,
                "revision_number": revision_number,
                "event": event.event_id,
            }
        )
        return MemoryRevision.create(
            memory_id=memory_id,
            revision_nonce=revision_nonce,
            revision_number=revision_number,
            parent_revision_refs=() if existing is None else (existing.ref,),
            memory_kind=request.memory_kind,
            namespace=request.target_namespace,
            content=request.candidate_content,
            provenance=provenance,
            retention_policy=request.retention_policy,
            formation_event_ref=event.event_id,
            created_by=request.actor.principal_id,
            idempotency_key="m1c-i2/"
            + canonical_sha256({"request_digest": request.request_digest}),
            created_at=request.now,
        )

    def _reserve(
        self,
        request: ConsolidationRequest,
        fingerprint: str,
    ) -> ConsolidationResult | str | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT request_fingerprint, result_json
                    FROM consolidation_idempotency WHERE idempotency_key = ?
                    """,
                    (request.idempotency_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO consolidation_idempotency(
                            idempotency_key, request_fingerprint,
                            request_digest, state, result_json
                        ) VALUES (?, ?, ?, 'IN_PROGRESS', NULL)
                        """,
                        (request.idempotency_key, fingerprint, request.request_digest),
                    )
                    connection.commit()
                    return None
                if row["request_fingerprint"] != fingerprint:
                    connection.commit()
                    return "REBOUND"
                if row["result_json"] is not None:
                    result = ConsolidationResult.model_validate_json(row["result_json"])
                    connection.commit()
                    return result
                connection.commit()
                return None
            except Exception:
                connection.rollback()
                raise

    def _budget_failure(
        self,
        request: ConsolidationRequest,
        fingerprint: str,
        event: ConsolidationEvent,
        proposal_digest: str,
        parents: tuple[_ParentRecord, ...],
        started: float,
        estimated_tokens: int,
        derivation_depth: int,
        reason: str,
    ) -> ConsolidationResult:
        return self._finish(
            request=request,
            fingerprint=fingerprint,
            event=event,
            status=ConsolidationStatus.BUDGET_EXHAUSTED,
            proposal_digest=proposal_digest,
            parents=parents,
            started=started,
            estimated_tokens=estimated_tokens,
            derivation_depth=derivation_depth,
            rejected_reasons=(reason,),
        )

    def _finish(
        self,
        *,
        request: ConsolidationRequest,
        fingerprint: str,
        event: ConsolidationEvent,
        status: ConsolidationStatus,
        proposal_digest: str,
        parents: tuple[_ParentRecord, ...],
        started: float,
        estimated_tokens: int = 0,
        derivation_depth: int = 0,
        candidate_revision_ref: str | None = None,
        candidate_content_hash: str | None = None,
        effective_lifecycle: LifecycleState | None = None,
        duplicate_ref: str | None = None,
        conflict_refs: tuple[str, ...] = (),
        rejected_reasons: tuple[str, ...] = (),
        store_audit_ref: str | None = None,
    ) -> ConsolidationResult:
        result, evidence = self._make_result(
            request=request,
            event=event,
            status=status,
            proposal_digest=proposal_digest,
            snapshots=tuple(item.snapshot for item in parents),
            started=started,
            estimated_tokens=estimated_tokens,
            derivation_depth=derivation_depth,
            candidate_revision_ref=candidate_revision_ref,
            candidate_content_hash=candidate_content_hash,
            effective_lifecycle=effective_lifecycle,
            duplicate_ref=duplicate_ref,
            conflict_refs=conflict_refs,
            rejected_reasons=rejected_reasons,
            store_audit_ref=store_audit_ref,
        )
        self._finalize(request, fingerprint, event, result, evidence)
        return result

    def _ephemeral_rejection(
        self,
        request: ConsolidationRequest,
        event: ConsolidationEvent,
        proposal_digest: str,
        started: float,
        reason: str,
    ) -> ConsolidationResult:
        return self._make_result(
            request=request,
            event=event,
            status=ConsolidationStatus.REJECTED,
            proposal_digest=proposal_digest,
            snapshots=(),
            started=started,
            rejected_reasons=(reason,),
        )[0]

    @staticmethod
    def _make_result(
        *,
        request: ConsolidationRequest,
        event: ConsolidationEvent,
        status: ConsolidationStatus,
        proposal_digest: str,
        snapshots: tuple[ParentSnapshot, ...],
        started: float,
        estimated_tokens: int = 0,
        derivation_depth: int = 0,
        candidate_revision_ref: str | None = None,
        candidate_content_hash: str | None = None,
        effective_lifecycle: LifecycleState | None = None,
        duplicate_ref: str | None = None,
        conflict_refs: tuple[str, ...] = (),
        rejected_reasons: tuple[str, ...] = (),
        store_audit_ref: str | None = None,
    ) -> tuple[ConsolidationResult, ConsolidationReplayEvidence]:
        evidence = ConsolidationReplayEvidence.create(
            request_digest=request.request_digest,
            event_hash=event.event_hash,
            parent_snapshots=snapshots,
            proposal_digest=proposal_digest,
            validator_profile_ref=request.validator_profile_ref,
            status=status,
            candidate_revision_ref=candidate_revision_ref,
            candidate_content_hash=candidate_content_hash,
            store_audit_ref=store_audit_ref,
        )
        result = ConsolidationResult(
            request_digest=request.request_digest,
            consolidation_event_ref=event.event_id,
            status=status,
            candidate_revision_ref=candidate_revision_ref,
            candidate_content_hash=candidate_content_hash,
            effective_lifecycle=effective_lifecycle,
            parent_snapshot_digest=evidence.parent_snapshot_digest,
            duplicate_ref=duplicate_ref,
            conflict_refs=conflict_refs,
            rejected_reasons=rejected_reasons,
            budget=ConsolidationBudgetConsumption(
                parent_count=len(snapshots),
                estimated_tokens=estimated_tokens,
                output_count=int(candidate_revision_ref is not None),
                derivation_depth=derivation_depth,
                elapsed_ms_before_store=max(
                    0, int((time.perf_counter() - started) * 1000)
                ),
            ),
            store_audit_ref=store_audit_ref,
            replay_evidence_digest=evidence.manifest_digest,
        )
        return result, evidence

    def _finalize(
        self,
        request: ConsolidationRequest,
        fingerprint: str,
        event: ConsolidationEvent,
        result: ConsolidationResult,
        evidence: ConsolidationReplayEvidence,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO consolidation_events(
                        event_id, request_digest, event_hash, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.request_digest,
                        event.event_hash,
                        event.model_dump_json(),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO consolidation_replay(
                        request_digest, manifest_digest, payload_json
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(request_digest) DO UPDATE SET
                        manifest_digest = excluded.manifest_digest,
                        payload_json = excluded.payload_json
                    """,
                    (
                        request.request_digest,
                        evidence.manifest_digest,
                        evidence.model_dump_json(),
                    ),
                )
                updated = connection.execute(
                    """
                    UPDATE consolidation_idempotency
                    SET state = 'DONE', result_json = ?
                    WHERE idempotency_key = ? AND request_fingerprint = ?
                    """,
                    (
                        result.model_dump_json(),
                        request.idempotency_key,
                        fingerprint,
                    ),
                )
                if updated.rowcount != 1:
                    raise MemoryContractError(
                        ErrorCode.INTEGRITY_FAILED,
                        "consolidation idempotency reservation changed before finalize",
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _proposal_digest(request: ConsolidationRequest) -> str:
        return canonical_sha256(
            {
                "memory_kind": request.memory_kind,
                "target_namespace": request.target_namespace,
                "candidate_content": request.candidate_content,
                "retention_policy": request.retention_policy,
            }
        )

    @staticmethod
    def _logical_digest(revision: MemoryRevision) -> str:
        return canonical_sha256(
            {
                "memory_kind": revision.memory_kind,
                "target_namespace": revision.namespace,
                "candidate_content": revision.content,
                "retention_policy": revision.retention_policy,
            }
        )

    @staticmethod
    def _memory_id(request: ConsolidationRequest) -> str:
        subject = request.semantic_subject_key or canonical_sha256(
            request.parent_memory_refs
        )
        digest = canonical_sha256(
            {
                "namespace": request.target_namespace.canonical,
                "memory_kind": request.memory_kind.value,
                "semantic_subject": subject,
            }
        )
        return f"mem_{digest[:32]}"


def _parse_memory_ref(ref: str) -> tuple[str, str]:
    memory_id, separator, revision_id = ref.partition("@")
    if (
        separator != "@"
        or not memory_id.startswith("mem_")
        or len(memory_id) != 36
        or not revision_id.startswith("rev_")
    ):
        raise ValueError("parent Memory ref must be an exact memory_id@revision_id")
    return memory_id, revision_id


def _creator_type(principal_type: PrincipalType) -> CreatorType:
    if principal_type is PrincipalType.USER:
        return CreatorType.HUMAN
    if principal_type is PrincipalType.AGENT:
        return CreatorType.AGENT
    return CreatorType.SERVICE


def _find_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            found.add(str(key).casefold())
            found.update(_find_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_find_keys(nested))
    return found
