from __future__ import annotations

import sqlite3

from ..memory_contracts import LifecycleState, MemoryRevision, StateEvent, canonical_sha256
from .consolidation import (
    BackgroundConsolidator as _BaseBackgroundConsolidator,
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
    """Public I2 consolidator with poisoning and lifecycle hardening."""

    @staticmethod
    def _state_from_metadata(
        connection: sqlite3.Connection,
        *,
        memory_id: str,
        revision_id: str,
    ) -> LifecycleState:
        del revision_id
        forgotten = connection.execute(
            "SELECT 1 FROM tombstones WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if forgotten is not None:
            return LifecycleState.FORGOTTEN
        head = connection.execute(
            "SELECT revision_id FROM heads WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if head is None:
            return LifecycleState.CANDIDATE
        row = connection.execute(
            """
            SELECT payload_json
            FROM state_events
            WHERE memory_id = ? AND revision_id = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (memory_id, head["revision_id"]),
        ).fetchone()
        if row is None:
            return LifecycleState.CANDIDATE
        return StateEvent.model_validate_json(row["payload_json"]).to_state

    def _validate_candidate(
        self,
        request: ConsolidationRequest,
        parents: tuple[_ParentRecord, ...],
    ) -> None:
        super()._validate_candidate(request, parents)
        if request.memory_kind.value == "SEMANTIC":
            claim = str(request.candidate_content["claim"]).casefold()
            if any(pattern in claim for pattern in _PROMPT_CONTROL_PATTERNS):
                raise ConsolidationAdmissionError("PROMPT_CONTROL_CLAIM_REJECTED")

    def _existing_target(
        self,
        request: ConsolidationRequest,
        memory_id: str,
    ) -> tuple[MemoryRevision | None, LifecycleState | None]:
        try:
            return super()._existing_target(request, memory_id)
        except ConsolidationAdmissionError as exc:
            if exc.reason == "FORGOTTEN_SUBJECT_CANNOT_RESURRECT":
                return None, LifecycleState.FORGOTTEN
            raise

    def _build_revision(
        self,
        *,
        request: ConsolidationRequest,
        event,
        parents: tuple[_ParentRecord, ...],
        memory_id: str,
        existing: MemoryRevision | None,
    ) -> MemoryRevision:
        revision = super()._build_revision(
            request=request,
            event=event,
            parents=parents,
            memory_id=memory_id,
            existing=existing,
        )
        store_idempotency_key = "m1c-i2/" + canonical_sha256(
            {"request_digest": request.request_digest}
        )
        return revision.model_copy(update={"idempotency_key": store_idempotency_key})
