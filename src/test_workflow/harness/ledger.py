from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import Field, model_validator

from .contracts import FrozenModel


class LedgerStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    MERGED = "MERGED"
    BLOCKED = "BLOCKED"


class ModuleTestEvidence(FrozenModel):
    unit_command: str | None = None
    unit_result: str | None = None
    integration_command: str | None = None
    integration_result: str | None = None
    asset_paths: tuple[str, ...] = ()


class ModuleLedgerEntry(FrozenModel):
    module_id: str
    title: str
    status: LedgerStatus
    code_paths: tuple[str, ...] = ()
    document_paths: tuple[str, ...] = ()
    test_evidence: ModuleTestEvidence = ModuleTestEvidence()
    branch: str | None = None
    pull_request: int | None = Field(default=None, ge=1)
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    ci_run: int | None = Field(default=None, ge=1)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_completion_evidence(self) -> ModuleLedgerEntry:
        if self.status in {LedgerStatus.VERIFIED, LedgerStatus.MERGED}:
            required = (
                self.code_paths,
                self.document_paths,
                self.test_evidence.unit_result,
                self.test_evidence.integration_result,
                self.test_evidence.asset_paths,
            )
            if not all(required):
                raise ValueError(
                    f"verified module {self.module_id} requires code, docs, unit, "
                    "integration and managed assets"
                )
        if self.status == LedgerStatus.MERGED and not self.commit:
            raise ValueError(f"merged module {self.module_id} requires a commit")
        return self


class ImplementationLedger(FrozenModel):
    project: str
    schema_version: int = Field(default=1, ge=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modules: tuple[ModuleLedgerEntry, ...]

    @model_validator(mode="after")
    def validate_unique_modules(self) -> ImplementationLedger:
        ids = [item.module_id for item in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("ledger module ids must be unique")
        return self

    def counts(self) -> dict[str, int]:
        result = {status.value: 0 for status in LedgerStatus}
        for item in self.modules:
            result[item.status.value] += 1
        return result

    def unfinished(self) -> tuple[ModuleLedgerEntry, ...]:
        return tuple(
            item
            for item in self.modules
            if item.status not in {LedgerStatus.VERIFIED, LedgerStatus.MERGED}
        )


def load_implementation_ledger(path: Path) -> ImplementationLedger:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ImplementationLedger.model_validate(payload)
