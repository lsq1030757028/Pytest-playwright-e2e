from __future__ import annotations

import sqlite3

from ..memory_contracts import AccessOperation
from ..memory_store import SQLiteMemoryStore
from .models_guarded import FormationRequest
from .runtime_guarded import FormationRuntime as _GuardedFormationRuntime


class FormationRuntime(_GuardedFormationRuntime):
    """Public Formation runtime that fences exact replay with current Primary truth."""

    def _current_authority_rejection(self, request: FormationRequest) -> str | None:
        try:
            current = SQLiteMemoryStore(self.db_path)
            append = current.evaluate_permission(
                actor=request.actor,
                namespace=request.target_namespace,
                operation=AccessOperation.APPEND_REVISION,
            )
            if not append.allowed:
                return "TARGET_NAMESPACE_APPEND_DENIED"
            read = current.evaluate_permission(
                actor=request.actor,
                namespace=request.target_namespace,
                operation=AccessOperation.READ_CONTENT,
            )
            if not read.allowed:
                return "TARGET_NAMESPACE_SOURCE_READ_DENIED"
            if current.get_tombstone(memory_id=self._memory_id(request)) is not None:
                return "FORGOTTEN_SUBJECT_CANNOT_RESURRECT"
        except sqlite3.Error:
            return "PRIMARY_STORE_UNAVAILABLE"
        return None
