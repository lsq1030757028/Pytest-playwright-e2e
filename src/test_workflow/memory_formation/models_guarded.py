from __future__ import annotations

from typing import Any

from pydantic import model_validator

from ..memory_contracts import canonical_sha256
from .models import FormationReplayEvidence as _BaseFormationReplayEvidence
from .models import FormationRequest as _BaseFormationRequest


class FrozenDict(dict[str, Any]):
    """Recursively immutable JSON object for Formation requests."""

    @staticmethod
    def _reject_mutation(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise TypeError("governed Formation JSON values are immutable")

    __setitem__ = _reject_mutation
    __delitem__ = _reject_mutation
    clear = _reject_mutation
    pop = _reject_mutation
    popitem = _reject_mutation
    setdefault = _reject_mutation
    update = _reject_mutation


class FormationRequest(_BaseFormationRequest):
    """Public FormationRequest with deep-frozen candidate content."""

    @model_validator(mode="after")
    def freeze_candidate_content(self) -> FormationRequest:
        object.__setattr__(
            self,
            "candidate_content",
            _deep_freeze(self.candidate_content),
        )
        return self


class FormationReplayEvidence(_BaseFormationReplayEvidence):
    """Replay manifest with complete admission/conflict decision evidence."""

    authority_digest: str
    expected_head_revision_id: str | None = None
    rejected_reasons: tuple[str, ...] = ()
    duplicate_ref: str | None = None
    conflict_refs: tuple[str, ...] = ()
    budget_digest: str

    @model_validator(mode="after")
    def validate_extended_manifest(self) -> FormationReplayEvidence:
        if self.manifest_digest != canonical_sha256(self.manifest_payload()):
            raise ValueError("extended Formation replay manifest mismatch")
        return self


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return FrozenDict({key: _deep_freeze(nested) for key, nested in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(nested) for nested in value)
    return value
