from __future__ import annotations

from pathlib import Path

import pytest

from test_workflow.harness.diagnosis import (
    CandidateRepairRunner,
    EvidenceItem,
    EvidenceType,
    FailureCategory,
    FailureEvidence,
    RepairKind,
    RepairProposal,
    RuleFirstDiagnoser,
    evidence_hash,
)


@pytest.mark.harness_integration
def test_locator_failure_is_diagnosed_and_safely_repaired(tmp_path: Path) -> None:
    target_dir = tmp_path / "tests/generated"
    target_dir.mkdir(parents=True)
    test_path = target_dir / "test_page.py"
    test_path.write_text(
        'ELEMENTS = {"save-button": True}\n\n'
        'def test_save_button_locator() -> None:\n'
        '    assert ELEMENTS["submit-button"]\n',
        encoding="utf-8",
    )
    summary = "locator submit-button not found"
    diagnosis = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="repair-golden",
            items=(
                EvidenceItem(
                    evidence_id="trace-locator",
                    evidence_type=EvidenceType.TRACEBACK,
                    source="pytest",
                    summary=summary,
                    content_hash=evidence_hash(summary),
                ),
            ),
        )
    )
    proposal = RepairProposal(
        repair_id="repair-locator-golden",
        kind=RepairKind.LOCATOR,
        file_path="tests/generated/test_page.py",
        find='ELEMENTS["submit-button"]',
        replace='ELEMENTS["save-button"]',
        evidence_refs=diagnosis.evidence_refs,
        rationale="use the stable available locator key",
    )
    verification = CandidateRepairRunner(tmp_path).verify(proposal, test_path)

    assert diagnosis.category == FailureCategory.TEST_DEFECT
    assert diagnosis.auto_repair_allowed is True
    assert verification.before_return_code != 0
    assert verification.after_return_code == 0
    assert verification.patch_applied is True
    assert verification.passed is True
    assert 'ELEMENTS["save-button"]' in test_path.read_text(encoding="utf-8")
