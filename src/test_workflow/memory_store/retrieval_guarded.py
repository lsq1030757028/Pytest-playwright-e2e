from __future__ import annotations

from ..memory_contracts import canonical_sha256
from .retrieval import (
    ProgressiveMemoryRetriever as _BaseProgressiveMemoryRetriever,
    RetrievalRequest,
    RetrievalResult,
    RetrievalStage,
)


class ProgressiveMemoryRetriever(_BaseProgressiveMemoryRetriever):
    """Public M1B retriever with complete fail-closed evidence reasons.

    The core retriever already enforces authority and release safety. This guard
    makes blocked coverage obligations explicit in the result evidence so a
    caller never has to infer why retrieval stopped.
    """

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        result = super().retrieve(request)
        omitted = list(result.omitted_reasons)

        if not result.released:
            if request.exact_refs and "EXACT_REF_UNRESOLVED" not in omitted:
                omitted.append("EXACT_REF_UNRESOLVED")
            if request.required_refs and "REQUIRED_REF_UNRESOLVED" not in omitted:
                omitted.append("REQUIRED_REF_UNRESOLVED")

        if (
            result.stage_reached is RetrievalStage.WARM
            and len(result.released) < request.minimum_releases
            and not request.cold_escalation_reason
            and "COLD_ESCALATION_REASON_REQUIRED" not in omitted
        ):
            omitted.append("COLD_ESCALATION_REASON_REQUIRED")

        if tuple(omitted) == result.omitted_reasons:
            return result

        acl_epoch, forget_epoch = self._authority_epochs(request)
        evidence_payload = {
            "request_digest": request.request_digest,
            "stage": result.stage_reached.value,
            "status": result.status.value,
            "released": [
                {
                    "ref": item.ref,
                    "hash": item.content_hash,
                    "score": item.fusion_score,
                }
                for item in result.released
            ],
            "omitted": tuple(omitted),
            "primary_snapshot": result.primary_snapshot,
            "index_snapshot": result.index_snapshot,
            "acl_epoch": acl_epoch,
            "forget_epoch": forget_epoch,
        }
        return result.model_copy(
            update={
                "omitted_reasons": tuple(omitted),
                "evidence_digest": canonical_sha256(evidence_payload),
            }
        )
