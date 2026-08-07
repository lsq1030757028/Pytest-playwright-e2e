from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..memory_contracts import LifecycleState


class MemoryRevisionFence(BaseModel):
    """Exact primary-store dependency required to remain true at commit time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_id: str = Field(pattern=r"^mem_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^rev_[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle_state: LifecycleState

    @property
    def ref(self) -> str:
        return f"{self.memory_id}@{self.revision_id}"
