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
    SafeRepairValidator,
    evidence_hash,
)


def item(
    evidence_id: str,
    evidence_type: EvidenceType,
    summary: str,
    **attributes,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source="test",
        summary=summary,
        content_hash=evidence_hash(summary),
        attributes=attributes,
    )


def test_unhealthy_environment_has_highest_deterministic_priority() -> None:
    result = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="run-1",
            items=(
                item("env", EvidenceType.ENVIRONMENT, "database unavailable", healthy=False),
                item("state", EvidenceType.STATE_PROBE, "oracle mismatch", oracle_mismatch=True),
            ),
        )
    )
    assert result.category == FailureCategory.ENVIRONMENT
    assert result.auto_repair_allowed is False


def test_requirement_conflict_is_not_auto_repaired() -> None:
    result = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="run-1",
            items=(item("req", EvidenceType.REQUIREMENT, "requirement_invariant_conflict"),),
            oracle_confirmed=False,
        )
    )
    assert result.category == FailureCategory.REQUIREMENT_CONFLICT
    assert result.auto_repair_allowed is False


def test_locator_failure_is_classified_as_repairable_test_defect() -> None:
    result = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="run-1",
            items=(item("trace", EvidenceType.TRACEBACK, "locator not found"),),
        )
    )
    assert result.category == FailureCategory.TEST_DEFECT
    assert result.auto_repair_allowed is True


def test_independent_state_probe_identifies_product_defect() -> None:
    result = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="run-1",
            items=(
                item(
                    "state",
                    EvidenceType.STATE_PROBE,
                    "persisted state contradicts oracle",
                    oracle_mismatch=True,
                ),
            ),
        )
    )
    assert result.category == FailureCategory.PRODUCT_DEFECT
    assert result.auto_repair_allowed is False


def test_inconsistent_timeout_history_is_flaky_not_auto_fixed() -> None:
    result = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="run-1",
            items=(item("history", EvidenceType.HISTORY, "intermittent timeout"),),
            previous_outcomes=("pass", "fail"),
        )
    )
    assert result.category == FailureCategory.FLAKY
    assert result.auto_repair_allowed is False


def proposal(find: str, replace: str, *, kind: RepairKind = RepairKind.LOCATOR) -> RepairProposal:
    return RepairProposal(
        repair_id="repair-1",
        kind=kind,
        file_path="tests/generated/test_page.py",
        find=find,
        replace=replace,
        evidence_refs=("trace",),
        rationale="update stable locator",
    )


def test_safe_repair_allows_bounded_locator_change() -> None:
    result = SafeRepairValidator().validate(
        proposal('get_by_role("button", name="Old")', 'get_by_role("button", name="New")')
    )
    assert result.allowed is True


def test_safe_repair_rejects_assertion_removal_sleep_and_production_file() -> None:
    removed = SafeRepairValidator().validate(proposal("assert result", "result"))
    sleep = SafeRepairValidator().validate(proposal("wait()", "time.sleep(5)"))
    production = SafeRepairValidator().validate(
        proposal("old", "new").model_copy(update={"file_path": "examples/demo_app/main.py"})
    )
    assert removed.allowed is False
    assert sleep.allowed is False
    assert production.allowed is False


def test_repair_runner_rejects_ambiguous_patch(tmp_path: Path) -> None:
    tests = tmp_path / "tests/generated"
    tests.mkdir(parents=True)
    target = tests / "test_page.py"
    target.write_text("old = 1\nold = 1\ndef test_x(): assert True\n", encoding="utf-8")
    with pytest.raises(ValueError, match="occur once"):
        CandidateRepairRunner(tmp_path).verify(proposal("old = 1", "old = 2"), target)
