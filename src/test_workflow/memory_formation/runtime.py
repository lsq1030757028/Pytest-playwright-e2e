from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from ..harness.artifacts import ArtifactStore
from ..memory_contracts import (
    AccessOperation,
    CreatorType,
    Decision,
    ErrorCode,
    LifecycleState,
    MemoryContractError,
    MemoryKind,
    MemoryRevision,
    PrincipalType,
    Provenance,
    TransformationKind,
    canonical_sha256,
)
from ..memory_store import SQLiteMemoryStore
from .models import (
    FormationBudgetConsumption,
    FormationEvent,
    FormationReplayEvidence,
    FormationRequest,
    FormationResult,
    FormationStatus,
    SourceClass,
)
from .resolver import ArtifactFormationResolver, FormationAdmissionError, ResolvedFormationInputs


_PROTECTED_AUTHORITY_KEYS = frozenset(
    {
        "oracle_override",
        "policy_override",
        "permission_override",
        "lifecycle_override",
        "assurance_override",
    }
)
_PROMPT_CONTROL_PATTERNS = (
    "ignore previous",
    "ignore all policies",
    "override policy",
    "grant permission",
    "system prompt",
    "execute shell",
)


class FormationRuntime:
    """M1C-I1 deterministic Hot Formation runtime.

    ArtifactStore owns immutable source/evidence bytes. SQLiteMemoryStore remains
    the sole governed Memory writer. Formation metadata is restart-safe but does
    not replace M1B CAS, lifecycle, provenance or audit authority.
    """

    def __init__(
        self,
        store: SQLiteMemoryStore,
        artifact_store: ArtifactStore,
    ) -> None:
        self.store = store
        self.db_path = Path(store.db_path)
        self.resolver = ArtifactFormationResolver(artifact_store)
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
                CREATE TABLE IF NOT EXISTS formation_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    request_fingerprint TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('IN_PROGRESS', 'DONE')),
                    result_json TEXT
                );

                CREATE TABLE IF NOT EXISTS formation_events (
                    event_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS formation_replay (
                    request_digest TEXT PRIMARY KEY,
                    manifest_digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def form(self, request: FormationRequest) -> FormationResult:
        started = time.perf_counter()
        proposal_digest = self._proposal_digest(request)
        memory_id = self._memory_id(request)
        event = FormationEvent.create(
            request=request,
            proposed_memory_id=memory_id,
            proposal_digest=proposal_digest,
        )
        request_fingerprint = canonical_sha256(
            {
                "actor_principal_id": request.actor.principal_id,
                "request_digest": request.request_digest,
            }
        )
        reservation = self._reserve_idempotency(
            request=request,
            request_fingerprint=request_fingerprint,
        )
        if isinstance(reservation, FormationResult):
            return reservation
        if reservation == "REBOUND":
            result, evidence = self._result(
                request=request,
                event=event,
                status=FormationStatus.REJECTED,
                source_evidence_digest=self._surface_source_digest(request),
                proposal_digest=proposal_digest,
                budget=self._budget(request, started, estimated_tokens=0),
                rejected_reasons=("IDEMPOTENCY_KEY_REBOUND",),
            )
            self._persist_event_only(event, evidence)
            return result

        permission = self.store.evaluate_permission(
            actor=request.actor,
            namespace=request.target_namespace,
            operation=AccessOperation.APPEND_REVISION,
        )
        if not permission.allowed:
            return self._finish_rejection(
                request=request,
                event=event,
                proposal_digest=proposal_digest,
                started=started,
                reason="TARGET_NAMESPACE_APPEND_DENIED",
            )

        try:
            resolved = self.resolver.resolve(request)
            self._validate_candidate(request, resolved)
        except FormationAdmissionError as exc:
            status = (
                FormationStatus.BUDGET_EXHAUSTED
                if "BUDGET" in exc.reason
                else FormationStatus.REJECTED
            )
            result, evidence = self._result(
                request=request,
                event=event,
                status=status,
                source_evidence_digest=self._surface_source_digest(request),
                proposal_digest=proposal_digest,
                budget=self._budget(request, started, estimated_tokens=0),
                rejected_reasons=(exc.reason,),
            )
            self._finalize(request, request_fingerprint, event, result, evidence)
            return result

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if elapsed_ms > 1000:
            result, evidence = self._result(
                request=request,
                event=event,
                status=FormationStatus.BUDGET_EXHAUSTED,
                source_evidence_digest=resolved.source_evidence_digest,
                proposal_digest=proposal_digest,
                budget=self._budget(
                    request,
                    started,
                    estimated_tokens=resolved.estimated_tokens,
                ),
                rejected_reasons=("HOT_LATENCY_BUDGET_EXHAUSTED",),
            )
            self._finalize(request, request_fingerprint, event, result, evidence)
            return result

        request_store = SQLiteMemoryStore(
            self.db_path,
            resolved_sources=resolved.resolved_sources,
            resolved_evidence=resolved.resolved_evidence,
        )
        existing = self._existing_head(request_store, request, memory_id)
        if existing is not None:
            duplicate = self._logical_candidate_digest_from_revision(existing) == proposal_digest
            if duplicate:
                result, evidence = self._result(
                    request=request,
                    event=event,
                    status=FormationStatus.DUPLICATE_SUPPRESSED,
                    source_evidence_digest=resolved.source_evidence_digest,
                    proposal_digest=proposal_digest,
                    budget=self._budget(
                        request,
                        started,
                        estimated_tokens=resolved.estimated_tokens,
                    ),
                    candidate_revision_ref=existing.ref,
                    candidate_content_hash=existing.content_hash,
                    effective_lifecycle=request_store.get_effective_state(
                        memory_id=existing.memory_id
                    ),
                    duplicate_ref=existing.ref,
                )
                self._finalize(request, request_fingerprint, event, result, evidence)
                return result
            if request.expected_head_revision_id != existing.revision_id:
                result, evidence = self._result(
                    request=request,
                    event=event,
                    status=FormationStatus.CONFLICT_REQUIRES_REVIEW,
                    source_evidence_digest=resolved.source_evidence_digest,
                    proposal_digest=proposal_digest,
                    budget=self._budget(
                        request,
                        started,
                        estimated_tokens=resolved.estimated_tokens,
                    ),
                    conflict_refs=(existing.ref,),
                    rejected_reasons=("SEMANTIC_SUBJECT_CONFLICT",),
                )
                self._finalize(request, request_fingerprint, event, result, evidence)
                return result
        elif request.expected_head_revision_id is not None:
            result, evidence = self._result(
                request=request,
                event=event,
                status=FormationStatus.CONFLICT_REQUIRES_REVIEW,
                source_evidence_digest=resolved.source_evidence_digest,
                proposal_digest=proposal_digest,
                budget=self._budget(
                    request,
                    started,
                    estimated_tokens=resolved.estimated_tokens,
                ),
                rejected_reasons=("EXPECTED_HEAD_NOT_FOUND",),
            )
            self._finalize(request, request_fingerprint, event, result, evidence)
            return result

        revision = self._build_revision(
            request=request,
            event=event,
            resolved=resolved,
            memory_id=memory_id,
            existing=existing,
        )
        store_result = request_store.append_revision(
            actor=request.actor,
            revision=revision,
            expected_head_revision_id=(existing.revision_id if existing is not None else None),
            correlation_id=f"formation/{request.request_id}",
        )

        if store_result.decision is Decision.ACCEPTED:
            lifecycle = request_store.get_effective_state(memory_id=revision.memory_id)
            if lifecycle is not LifecycleState.CANDIDATE:
                raise MemoryContractError(
                    ErrorCode.INTEGRITY_FAILED,
                    "M1C formation produced a non-Candidate lifecycle",
                )
            status = (
                FormationStatus.CREATED_CANDIDATE
                if existing is None
                else FormationStatus.APPENDED_CANDIDATE_REVISION
            )
            result, evidence = self._result(
                request=request,
                event=event,
                status=status,
                source_evidence_digest=resolved.source_evidence_digest,
                proposal_digest=proposal_digest,
                budget=self._budget(
                    request,
                    started,
                    estimated_tokens=resolved.estimated_tokens,
                ),
                candidate_revision_ref=revision.ref,
                candidate_content_hash=revision.content_hash,
                effective_lifecycle=lifecycle,
                store_audit_ref=store_result.audit_event_ref,
            )
        elif store_result.decision is Decision.CONFLICT:
            current = self._existing_head(request_store, request, memory_id)
            if (
                current is not None
                and self._logical_candidate_digest_from_revision(current) == proposal_digest
            ):
                status = FormationStatus.DUPLICATE_SUPPRESSED
                duplicate_ref = current.ref
                conflict_refs: tuple[str, ...] = ()
                candidate_ref = current.ref
                candidate_hash = current.content_hash
                lifecycle = request_store.get_effective_state(memory_id=current.memory_id)
                reasons: tuple[str, ...] = ()
            else:
                status = FormationStatus.CONFLICT_REQUIRES_REVIEW
                duplicate_ref = None
                conflict_refs = tuple(
                    ref
                    for ref in (
                        current.ref if current is not None else None,
                        revision.ref,
                    )
                    if ref is not None
                )
                candidate_ref = None
                candidate_hash = None
                lifecycle = None
                reasons = ("STORE_CAS_CONFLICT",)
            result, evidence = self._result(
                request=request,
                event=event,
                status=status,
                source_evidence_digest=resolved.source_evidence_digest,
                proposal_digest=proposal_digest,
                budget=self._budget(
                    request,
                    started,
                    estimated_tokens=resolved.estimated_tokens,
                ),
                candidate_revision_ref=candidate_ref,
                candidate_content_hash=candidate_hash,
                effective_lifecycle=lifecycle,
                duplicate_ref=duplicate_ref,
                conflict_refs=conflict_refs,
                rejected_reasons=reasons,
            )
        else:
            result, evidence = self._result(
                request=request,
                event=event,
                status=FormationStatus.REJECTED,
                source_evidence_digest=resolved.source_evidence_digest,
                proposal_digest=proposal_digest,
                budget=self._budget(
                    request,
                    started,
                    estimated_tokens=resolved.estimated_tokens,
                ),
                rejected_reasons=(
                    store_result.error_code.value
                    if store_result.error_code is not None
                    else "STORE_REJECTED",
                ),
            )

        self._finalize(request, request_fingerprint, event, result, evidence)
        return result

    def replay_evidence(self, request_digest: str) -> FormationReplayEvidence:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload_json FROM formation_replay WHERE request_digest = ?",
                (request_digest,),
            ).fetchone()
        if row is None:
            raise KeyError(request_digest)
        return FormationReplayEvidence.model_validate_json(row["payload_json"])

    def _validate_candidate(
        self,
        request: FormationRequest,
        resolved: ResolvedFormationInputs,
    ) -> None:
        if request.historical_only and request.memory_kind is not MemoryKind.EPISODIC:
            raise FormationAdmissionError("HISTORICAL_FORMATION_REQUIRES_EPISODIC_KIND")
        blocked_keys = _find_keys(request.candidate_content) & _PROTECTED_AUTHORITY_KEYS
        if blocked_keys:
            raise FormationAdmissionError("PROTECTED_AUTHORITY_MUTATION_ATTEMPT")

        current_requirement_sources = {
            source.source_ref
            for source in request.sources
            if source.source_class is SourceClass.REQUIREMENT_REVISION
            and not source.historical_only
        }
        if current_requirement_sources and not current_requirement_sources <= set(
            request.authority_refs
        ):
            raise FormationAdmissionError("CURRENT_REQUIREMENT_AUTHORITY_UNBOUND")

        if request.memory_kind is MemoryKind.SEMANTIC:
            claim = request.candidate_content.get("claim")
            if not isinstance(claim, str) or not claim.strip():
                raise FormationAdmissionError("SEMANTIC_CLAIM_REQUIRED")
            lowered = claim.casefold()
            if any(pattern in lowered for pattern in _PROMPT_CONTROL_PATTERNS):
                raise FormationAdmissionError("PROMPT_INJECTION_SEMANTIC_CLAIM")
            supported = any(
                claim in resolved.source_text_by_ref[source_ref]
                for source_ref in request.supporting_source_refs
            )
            if not supported:
                raise FormationAdmissionError("UNSUPPORTED_SEMANTIC_CLAIM")

    def _build_revision(
        self,
        *,
        request: FormationRequest,
        event: FormationEvent,
        resolved: ResolvedFormationInputs,
        memory_id: str,
        existing: MemoryRevision | None,
    ) -> MemoryRevision:
        revision_number = 1 if existing is None else existing.revision_number + 1
        parents = () if existing is None else (existing.ref,)
        transformation = {
            MemoryKind.EPISODIC: TransformationKind.SUMMARY,
            MemoryKind.SEMANTIC: TransformationKind.EXTRACTION,
            MemoryKind.WORKING: TransformationKind.RAW_OBSERVATION,
        }[request.memory_kind]
        provenance = Provenance(
            source_refs=tuple(source.source_ref for source in request.sources),
            evidence_refs=resolved.resolved_evidence,
            source_content_hashes=resolved.resolved_sources,
            created_by_principal=request.actor.principal_id,
            creator_type=_creator_type(request.actor.principal_type),
            capability_or_formation_rule_ref=request.formation_rule_ref,
            requirement_revision_refs=(
                request.requirement_revision_refs
                or tuple(
                    source.source_ref
                    for source in request.sources
                    if source.source_class is SourceClass.REQUIREMENT_REVISION
                )
            ),
            code_revision_refs=(
                request.code_revision_refs
                or tuple(
                    source.source_ref
                    for source in request.sources
                    if source.source_class is SourceClass.CODE_REVISION
                )
            ),
            environment_revision_refs=(
                request.environment_revision_refs
                or tuple(
                    source.source_ref
                    for source in request.sources
                    if source.source_class is SourceClass.ENVIRONMENT_REVISION
                )
            ),
            parent_memory_refs=parents,
            transformation_kind=transformation,
        )
        revision_nonce = canonical_sha256(
            {
                "request_digest": request.request_digest,
                "memory_id": memory_id,
                "revision_number": revision_number,
                "formation_event": event.event_id,
            }
        )
        return MemoryRevision.create(
            memory_id=memory_id,
            revision_nonce=revision_nonce,
            revision_number=revision_number,
            parent_revision_refs=parents,
            memory_kind=request.memory_kind,
            namespace=request.target_namespace,
            content=request.candidate_content,
            provenance=provenance,
            retention_policy=request.retention_policy,
            formation_event_ref=event.event_id,
            created_by=request.actor.principal_id,
            idempotency_key=request.idempotency_key,
            created_at=request.now,
        )

    def _reserve_idempotency(
        self,
        *,
        request: FormationRequest,
        request_fingerprint: str,
    ) -> FormationResult | str | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT request_fingerprint, result_json
                    FROM formation_idempotency
                    WHERE idempotency_key = ?
                    """,
                    (request.idempotency_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO formation_idempotency(
                            idempotency_key, request_fingerprint,
                            request_digest, state, result_json
                        ) VALUES (?, ?, ?, 'IN_PROGRESS', NULL)
                        """,
                        (
                            request.idempotency_key,
                            request_fingerprint,
                            request.request_digest,
                        ),
                    )
                    connection.commit()
                    return None
                if row["request_fingerprint"] != request_fingerprint:
                    connection.commit()
                    return "REBOUND"
                if row["result_json"] is not None:
                    result = FormationResult.model_validate_json(row["result_json"])
                    connection.commit()
                    return result
                connection.commit()
                return None
            except Exception:
                connection.rollback()
                raise

    def _finalize(
        self,
        request: FormationRequest,
        request_fingerprint: str,
        event: FormationEvent,
        result: FormationResult,
        evidence: FormationReplayEvidence,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT payload_json FROM formation_events WHERE event_id = ?",
                    (event.event_id,),
                ).fetchone()
                if existing is not None:
                    persisted = FormationEvent.model_validate_json(existing["payload_json"])
                    if persisted != event:
                        raise MemoryContractError(
                            ErrorCode.INTEGRITY_FAILED,
                            "formation event identity was rebound",
                        )
                else:
                    connection.execute(
                        """
                        INSERT INTO formation_events(
                            event_id, request_digest, event_hash, payload_json
                        )
                        VALUES (?, ?, ?, ?)
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
                    INSERT INTO formation_replay(request_digest, manifest_digest, payload_json)
                    VALUES (?, ?, ?)
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
                    UPDATE formation_idempotency
                    SET state = 'DONE', result_json = ?
                    WHERE idempotency_key = ? AND request_fingerprint = ?
                    """,
                    (
                        result.model_dump_json(),
                        request.idempotency_key,
                        request_fingerprint,
                    ),
                )
                if updated.rowcount != 1:
                    raise MemoryContractError(
                        ErrorCode.INTEGRITY_FAILED,
                        "formation idempotency reservation changed before finalize",
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _persist_event_only(
        self,
        event: FormationEvent,
        evidence: FormationReplayEvidence,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO formation_events(
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
                    INSERT OR IGNORE INTO formation_replay(
                        request_digest, manifest_digest, payload_json
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        event.request_digest,
                        evidence.manifest_digest,
                        evidence.model_dump_json(),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _finish_rejection(
        self,
        *,
        request: FormationRequest,
        event: FormationEvent,
        proposal_digest: str,
        started: float,
        reason: str,
    ) -> FormationResult:
        fingerprint = canonical_sha256(
            {
                "actor_principal_id": request.actor.principal_id,
                "request_digest": request.request_digest,
            }
        )
        result, evidence = self._result(
            request=request,
            event=event,
            status=FormationStatus.REJECTED,
            source_evidence_digest=self._surface_source_digest(request),
            proposal_digest=proposal_digest,
            budget=self._budget(request, started, estimated_tokens=0),
            rejected_reasons=(reason,),
        )
        self._finalize(request, fingerprint, event, result, evidence)
        return result

    def _result(
        self,
        *,
        request: FormationRequest,
        event: FormationEvent,
        status: FormationStatus,
        source_evidence_digest: str,
        proposal_digest: str,
        budget: FormationBudgetConsumption,
        candidate_revision_ref: str | None = None,
        candidate_content_hash: str | None = None,
        effective_lifecycle: LifecycleState | None = None,
        duplicate_ref: str | None = None,
        conflict_refs: tuple[str, ...] = (),
        rejected_reasons: tuple[str, ...] = (),
        store_audit_ref: str | None = None,
    ) -> tuple[FormationResult, FormationReplayEvidence]:
        evidence_payload = {
            "request_digest": request.request_digest,
            "formation_event_hash": event.event_hash,
            "source_evidence_digest": source_evidence_digest,
            "proposal_digest": proposal_digest,
            "validator_profile_ref": request.validator_profile_ref,
            "status": status,
            "candidate_revision_ref": candidate_revision_ref,
            "candidate_content_hash": candidate_content_hash,
            "store_audit_ref": store_audit_ref,
        }
        evidence = FormationReplayEvidence(
            **evidence_payload,
            manifest_digest=canonical_sha256(evidence_payload),
        )
        result = FormationResult(
            request_digest=request.request_digest,
            formation_event_ref=event.event_id,
            status=status,
            candidate_revision_ref=candidate_revision_ref,
            candidate_content_hash=candidate_content_hash,
            effective_lifecycle=effective_lifecycle,
            source_evidence_digest=source_evidence_digest,
            duplicate_ref=duplicate_ref,
            conflict_refs=conflict_refs,
            rejected_reasons=rejected_reasons,
            budget=budget,
            validator_profile_ref=request.validator_profile_ref,
            store_audit_ref=store_audit_ref,
            replay_evidence_digest=evidence.manifest_digest,
        )
        return result, evidence

    @staticmethod
    def _budget(
        request: FormationRequest,
        started: float,
        *,
        estimated_tokens: int,
    ) -> FormationBudgetConsumption:
        return FormationBudgetConsumption(
            source_count=len(request.sources),
            evidence_count=len(request.evidence),
            estimated_tokens=estimated_tokens,
            elapsed_ms_before_store=max(0, int((time.perf_counter() - started) * 1000)),
        )

    @staticmethod
    def _proposal_digest(request: FormationRequest) -> str:
        return canonical_sha256(
            {
                "memory_kind": request.memory_kind,
                "target_namespace": request.target_namespace,
                "candidate_content": request.candidate_content,
                "retention_policy": request.retention_policy,
                "semantic_subject_key": request.semantic_subject_key,
            }
        )

    @staticmethod
    def _logical_candidate_digest_from_revision(revision: MemoryRevision) -> str:
        return canonical_sha256(
            {
                "memory_kind": revision.memory_kind,
                "target_namespace": revision.namespace,
                "candidate_content": revision.content,
                "retention_policy": revision.retention_policy,
                "semantic_subject_key": None,
            }
        )

    @staticmethod
    def _memory_id(request: FormationRequest) -> str:
        subject = request.semantic_subject_key or request.request_digest
        digest = canonical_sha256(
            {
                "namespace": request.target_namespace.canonical,
                "memory_kind": request.memory_kind.value,
                "semantic_subject": subject,
            }
        )
        return f"mem_{digest[:32]}"

    @staticmethod
    def _surface_source_digest(request: FormationRequest) -> str:
        return canonical_sha256(
            {
                "sources": [source.model_dump(mode="json") for source in request.sources],
                "evidence": [item.model_dump(mode="json") for item in request.evidence],
                "authority_refs": request.authority_refs,
            }
        )

    @staticmethod
    def _existing_head(
        store: SQLiteMemoryStore,
        request: FormationRequest,
        memory_id: str,
    ) -> MemoryRevision | None:
        try:
            return store.get_head_revision(actor=request.actor, memory_id=memory_id)
        except MemoryContractError as exc:
            if exc.code is ErrorCode.MEMORY_NOT_FOUND:
                return None
            if exc.code is ErrorCode.FORGOTTEN_CONTENT_UNAVAILABLE:
                raise FormationAdmissionError("FORGOTTEN_SUBJECT_CANNOT_RESURRECT") from exc
            raise


def _creator_type(principal_type: PrincipalType) -> CreatorType:
    if principal_type is PrincipalType.USER:
        return CreatorType.HUMAN
    if principal_type is PrincipalType.AGENT:
        return CreatorType.AGENT
    if principal_type is PrincipalType.SERVICE:
        return CreatorType.SERVICE
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
