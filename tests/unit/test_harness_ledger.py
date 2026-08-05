from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from test_workflow.harness.ledger import (
    ImplementationLedger,
    LedgerStatus,
    ModuleLedgerEntry,
    ModuleTestEvidence,
)


def evidence() -> ModuleTestEvidence:
    return ModuleTestEvidence(
        unit_command="pytest unit",
        unit_result="PASS",
        integration_command="pytest integration",
        integration_result="PASS",
        asset_paths=("tests/assets/module",),
    )


def test_verified_module_requires_complete_evidence() -> None:
    with pytest.raises(ValidationError, match="requires code"):
        ModuleLedgerEntry(
            module_id="module",
            title="Module",
            status=LedgerStatus.VERIFIED,
        )


def test_merged_module_requires_commit() -> None:
    with pytest.raises(ValidationError, match="requires a commit"):
        ModuleLedgerEntry(
            module_id="module",
            title="Module",
            status=LedgerStatus.MERGED,
            code_paths=("src/module.py",),
            document_paths=("docs/module.md",),
            test_evidence=evidence(),
        )


def test_ledger_rejects_duplicate_module_ids() -> None:
    entry = ModuleLedgerEntry(
        module_id="module",
        title="Module",
        status=LedgerStatus.IMPLEMENTED,
    )
    with pytest.raises(ValidationError, match="unique"):
        ImplementationLedger(
            project="project",
            updated_at=datetime.now(UTC),
            modules=(entry, entry),
        )


def test_ledger_counts_and_unfinished() -> None:
    ledger = ImplementationLedger(
        project="project",
        modules=(
            ModuleLedgerEntry(
                module_id="verified",
                title="Verified",
                status=LedgerStatus.VERIFIED,
                code_paths=("src/verified.py",),
                document_paths=("docs/verified.md",),
                test_evidence=evidence(),
            ),
            ModuleLedgerEntry(
                module_id="pending",
                title="Pending",
                status=LedgerStatus.IMPLEMENTED,
            ),
        ),
    )
    assert ledger.counts()["VERIFIED"] == 1
    assert [item.module_id for item in ledger.unfinished()] == ["pending"]
