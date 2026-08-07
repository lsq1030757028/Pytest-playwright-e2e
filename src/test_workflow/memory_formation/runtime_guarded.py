from __future__ import annotations

import time

from ..memory_contracts import (
    AccessOperation,
    MemoryKind,
    MemoryRevision,
    canonical_sha256,
)
from .integrity import verify_formation_integrity
from .models import FormationEvent, FormationRequest, FormationStatus
from .poisoning import contains_control_instruction
from .resolver import FormationAdmissionError, ResolvedFormationInputs
from .runtime import FormationRuntime as _BaseFormationRuntime


class FormationRuntime(_BaseFormationRuntime):
    """Public I1 runtime with authority, poisoning and replay guards."""

    @staticmethod
    def _proposal_digest(request: FormationRequest) -> str:
        # semantic_subject_key already determines the logical memory_id. Keeping
        # it out of the candidate digest lets same-subject/same-content requests
        # suppress duplicates rather than manufacture a false conflict.
        return canonical_sha256(
            {
                "memory_kind": request.memory_kind,
                "target_namespace": request.target_namespace,
                "candidate_content": request.candidate_content,
                "retention_policy": request.retention_policy,
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
            }
        )

    def _validate_candidate(
        self,
        request: FormationRequest,
        resolved: ResolvedFormationInputs,
    ) -> None:
        super()._validate_candidate(request, resolved)
        if request.memory_kind is MemoryKind.SEMANTIC:
            claim = request.candidate_content.get("claim")
            if isinstance(claim, str) and contains_control_instruction(claim):
                raise FormationAdmissionError("PROMPT_CONTROL_CLAIM_REJECTED")

    def form(self, request: FormationRequest):
        # Tampered durable formation/consolidation evidence invalidates further
        # formation work until the Store is repaired/recovered.
        verify_formation_integrity(self.db_path)

        # Target authority must be proven before *any* Formation-owned durable
        # mutation, including idempotency reservation. Otherwise an unauthorized
        # actor could squat a guessed idempotency key and deny a later authorized
        # request. The base runtime repeats this check before source admission.
        permission = self.store.evaluate_permission(
            actor=request.actor,
            namespace=request.target_namespace,
            operation=AccessOperation.APPEND_REVISION,
        )
        if not permission.allowed:
            started = time.perf_counter()
            proposal_digest = self._proposal_digest(request)
            event = FormationEvent.create(
                request=request,
                proposed_memory_id=self._memory_id(request),
                proposal_digest=proposal_digest,
            )
            result, _evidence = self._result(
                request=request,
                event=event,
                status=FormationStatus.REJECTED,
                source_evidence_digest=self._surface_source_digest(request),
                proposal_digest=proposal_digest,
                budget=self._budget(request, started, estimated_tokens=0),
                rejected_reasons=("TARGET_NAMESPACE_APPEND_DENIED",),
            )
            return result

        try:
            return super().form(request)
        except FormationAdmissionError as exc:
            # The base runtime handles ordinary admission failures internally.
            # This path covers an authoritative head lookup discovering a
            # forgotten deterministic subject ID: it must become an explicit
            # no-write result, never an exception-driven resurrection path.
            started = time.perf_counter()
            proposal_digest = self._proposal_digest(request)
            event = FormationEvent.create(
                request=request,
                proposed_memory_id=self._memory_id(request),
                proposal_digest=proposal_digest,
            )
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
                rejected_reasons=(exc.reason,),
            )
            self._finalize(request, fingerprint, event, result, evidence)
            return result
