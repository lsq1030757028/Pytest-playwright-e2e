from __future__ import annotations

from dataclasses import dataclass

from ..harness.artifacts import ArtifactStore, canonical_json_bytes
from ..harness.contracts import ArtifactValidity
from ..memory_contracts import MemoryKind, canonical_sha256
from .models import FormationRequest


class FormationAdmissionError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ResolvedFormationInputs:
    resolved_sources: dict[str, str]
    resolved_evidence: tuple[str, ...]
    source_text_by_ref: dict[str, str]
    source_evidence_digest: str
    estimated_tokens: int


class ArtifactFormationResolver:
    """Resolve immutable Formation inputs without granting authority.

    ArtifactStore.get(ArtifactRef) verifies that the stored immutable envelope
    exactly matches the caller-supplied ref and its content hash. M1C-I1 keeps
    source/evidence namespaces equal to the target namespace; broader governed
    consolidation is reserved for I2.
    """

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def resolve(self, request: FormationRequest) -> ResolvedFormationInputs:
        resolved_sources: dict[str, str] = {}
        resolved_evidence: list[str] = []
        source_text_by_ref: dict[str, str] = {}
        digest_sources: list[dict[str, object]] = []
        digest_evidence: list[dict[str, object]] = []
        estimated_bytes = len(canonical_json_bytes(request.candidate_content))

        for source in request.sources:
            if source.namespace != request.target_namespace:
                raise FormationAdmissionError("CROSS_NAMESPACE_SOURCE_DENIED")
            if source.evaluator_only or source.holdout:
                raise FormationAdmissionError("EVALUATOR_OR_HOLDOUT_CONTAMINATION")
            if source.sensitive:
                raise FormationAdmissionError("SENSITIVE_SOURCE_FORBIDDEN")
            if (
                source.historical_only
                and request.memory_kind is not MemoryKind.EPISODIC
                and not request.historical_only
            ):
                raise FormationAdmissionError("STALE_AUTHORITY_SOURCE")
            try:
                envelope = self.artifact_store.get(source.artifact_ref)
            except Exception as exc:
                raise FormationAdmissionError("SOURCE_ARTIFACT_UNRESOLVED") from exc
            if envelope.ref.validity is ArtifactValidity.INVALID:
                raise FormationAdmissionError("SOURCE_ARTIFACT_INVALID")
            if envelope.ref.validity is ArtifactValidity.HISTORICAL and not source.historical_only:
                raise FormationAdmissionError("UNLABELED_HISTORICAL_SOURCE")

            resolved_sources[source.source_ref] = source.source_hash
            encoded = canonical_json_bytes(envelope.content)
            source_text_by_ref[source.source_ref] = encoded.decode("utf-8")
            estimated_bytes += len(encoded)
            digest_sources.append(
                {
                    "source_ref": source.source_ref,
                    "source_hash": source.source_hash,
                    "source_class": source.source_class.value,
                    "historical_only": source.historical_only,
                }
            )

        for evidence in request.evidence:
            if evidence.namespace != request.target_namespace:
                raise FormationAdmissionError("CROSS_NAMESPACE_EVIDENCE_DENIED")
            if evidence.evaluator_only or evidence.holdout:
                raise FormationAdmissionError("EVALUATOR_OR_HOLDOUT_CONTAMINATION")
            if evidence.sensitive:
                raise FormationAdmissionError("SENSITIVE_EVIDENCE_FORBIDDEN")
            try:
                envelope = self.artifact_store.get(evidence.artifact_ref)
            except Exception as exc:
                raise FormationAdmissionError("EVIDENCE_ARTIFACT_UNRESOLVED") from exc
            if envelope.ref.validity is not ArtifactValidity.VALID:
                raise FormationAdmissionError("EVIDENCE_ARTIFACT_NOT_CURRENT_VALID")
            resolved_evidence.append(evidence.evidence_ref)
            estimated_bytes += len(canonical_json_bytes(envelope.content))
            digest_evidence.append(
                {
                    "evidence_ref": evidence.evidence_ref,
                    "content_hash": envelope.ref.content_hash,
                }
            )

        estimated_tokens = max(1, (estimated_bytes + 3) // 4)
        if estimated_tokens > 4000:
            raise FormationAdmissionError("HOT_TOKEN_BUDGET_EXHAUSTED")
        if len(request.sources) > 16 or len(request.evidence) > 16:
            raise FormationAdmissionError("HOT_SOURCE_BUDGET_EXHAUSTED")

        source_evidence_digest = canonical_sha256(
            {
                "sources": digest_sources,
                "evidence": digest_evidence,
                "authority_refs": request.authority_refs,
            }
        )
        return ResolvedFormationInputs(
            resolved_sources=resolved_sources,
            resolved_evidence=tuple(resolved_evidence),
            source_text_by_ref=source_text_by_ref,
            source_evidence_digest=source_evidence_digest,
            estimated_tokens=estimated_tokens,
        )
