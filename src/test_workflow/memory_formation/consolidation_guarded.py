from __future__ import annotations

from ..memory_contracts import MemoryKind
from .consolidation import BackgroundConsolidator as _BaseBackgroundConsolidator
from .consolidation import (
    ConsolidationAdmissionError,
    ConsolidationRequest,
    _ParentRecord,
)
from .contamination import MemoryContaminationRegistry
from .integrity import verify_formation_integrity
from .poisoning import contains_control_instruction

_AUTHORITY_PREFIXES = ("requirement/", "code/", "environment/")


class BackgroundConsolidator(_BaseBackgroundConsolidator):
    """Public I2/I3 consolidator with poisoning and authority hardening."""

    def __init__(self, store) -> None:
        super().__init__(store)
        self.contamination = MemoryContaminationRegistry(self.db_path)

    def consolidate(self, request: ConsolidationRequest):
        verify_formation_integrity(self.db_path)
        return super().consolidate(request)

    def _admit_parents(
        self,
        request: ConsolidationRequest,
    ) -> tuple[_ParentRecord, ...]:
        # Contamination metadata is checked before the base admission pipeline
        # parses any parent payload_json. This prevents evaluator/holdout content
        # from influencing candidate proposal or evidence surfaces.
        if self.contamination.records_for_refs(request.parent_memory_refs):
            raise ConsolidationAdmissionError("PARENT_CONTAMINATED")
        return super()._admit_parents(request)

    def _validate_candidate(
        self,
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> None:
        super()._validate_candidate(request, parents)
        self._validate_authority_binding(request, parents)
        if request.memory_kind is MemoryKind.SEMANTIC:
            claim = str(request.candidate_content["claim"])
            if contains_control_instruction(claim):
                raise ConsolidationAdmissionError("PROMPT_CONTROL_CLAIM_REJECTED")

    @staticmethod
    def _validate_authority_binding(
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> None:
        declared = {
            ref for ref in request.authority_refs if ref.startswith(_AUTHORITY_PREFIXES)
        }
        if not declared:
            return

        proven: set[str] = set()
        for parent in parents:
            provenance = parent.revision.provenance
            proven.update(provenance.requirement_revision_refs)
            proven.update(provenance.code_revision_refs)
            proven.update(provenance.environment_revision_refs)

        if not declared <= proven:
            raise ConsolidationAdmissionError("AUTHORITY_REF_UNBOUND")
