from __future__ import annotations

from ..memory_contracts import MemoryKind
from .consolidation import BackgroundConsolidator as _BaseBackgroundConsolidator
from .consolidation import (
    ConsolidationAdmissionError,
    ConsolidationRequest,
    _ParentRecord,
)

_PROMPT_CONTROL_PATTERNS = (
    "ignore previous",
    "ignore all policies",
    "override policy",
    "grant permission",
    "system prompt",
    "execute shell",
)
_AUTHORITY_PREFIXES = ("requirement/", "code/", "environment/")


class BackgroundConsolidator(_BaseBackgroundConsolidator):
    """Public I2 consolidator with poisoning and authority hardening."""

    def _validate_candidate(
        self,
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> None:
        super()._validate_candidate(request, parents)
        self._validate_authority_binding(request, parents)
        if request.memory_kind is MemoryKind.SEMANTIC:
            claim = str(request.candidate_content["claim"]).casefold()
            if any(pattern in claim for pattern in _PROMPT_CONTROL_PATTERNS):
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
