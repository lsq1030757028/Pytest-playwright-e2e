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


class BackgroundConsolidator(_BaseBackgroundConsolidator):
    """Public I2 consolidator with poisoning hardening."""

    def _validate_candidate(
        self,
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> None:
        super()._validate_candidate(request, parents)
        if request.memory_kind is MemoryKind.SEMANTIC:
            claim = str(request.candidate_content["claim"]).casefold()
            if any(pattern in claim for pattern in _PROMPT_CONTROL_PATTERNS):
                raise ConsolidationAdmissionError("PROMPT_CONTROL_CLAIM_REJECTED")
