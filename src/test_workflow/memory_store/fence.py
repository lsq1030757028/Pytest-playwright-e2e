from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..memory_contracts import LifecycleState


class MemoryRevisionFence(BaseModel):
    """Exact primary-store dependency required to remain true at commit time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^rev_[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle_state: LifecycleState

    @model_validator(mode="after")
    def validate_lifecycle(self) -> MemoryRevisionFence:
        if self.lifecycle_state in {
            LifecycleState.REVOKED,
            LifecycleState.EXPIRED,
            LifecycleState.FORGOTTEN,
            LifecycleState.SUPERSEDED,
            LifecycleState.CONFLICTING,
            LifecycleState.QUARANTINED,
        }:
            raise ValueError("parent fence must bind an admissible lifecycle state")
        return self

    @property
    def ref(self) -> str:
        return f"{self.memory_id}@{self.revision_id}"
