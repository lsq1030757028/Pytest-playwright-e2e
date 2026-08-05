from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "docs/specs/ux0-synthetic-user-agent.yaml"
APPROVAL_PATH = ROOT / "docs/specs/ux0-synthetic-user-agent-approval.yaml"
STATUS_PATH = ROOT / "docs/ux-assurance-status.md"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_candidate_spec_has_versioned_merge_approval() -> None:
    spec = load_yaml(SPEC_PATH)
    approval = load_yaml(APPROVAL_PATH)

    assert spec["status"] == "CANDIDATE"
    assert approval["approval_id"] == "APPROVAL-UX0-SYNTHETIC-USER-SPEC"
    assert approval["version"] == "1.0.0"
    assert approval["status"] == "ACTIVE_WHEN_MERGED"
    assert approval["spec_ref"] == (
        f"{spec['spec_id']}@{spec['version']}"
    )
    assert approval["candidate_status"] == "CANDIDATE"
    assert approval["goal_issue"] == spec["goal_issue"] == 29
    assert approval["pull_request"] == 30
    assert approval["mandate_ref"] == spec["mandate_ref"]
    assert approval["scope"] == spec["scope_kind"]
    assert approval["assurance"] == "DEV3"


def test_approval_is_bound_to_green_focused_and_full_evidence() -> None:
    approval = load_yaml(APPROVAL_PATH)
    focused = approval["approval_basis"]["focused_spec_run"]
    full = approval["approval_basis"]["full_repository_run"]
    review = approval["approval_basis"]["review_requirements"]

    assert focused["id"] == 30984682783
    assert focused["run_number"] == 2
    assert focused["result"] == "PASS"
    assert focused["tests"] == 12
    assert focused["failed"] == 0
    assert focused["artifact_id"] == 8921568099
    assert focused["artifact_digest"].startswith("sha256:")
    assert full["id"] == 30984682730
    assert full["run_number"] == 102
    assert full["result"] == "PASS"
    assert full["artifact_id"] == 8921629226
    assert full["artifact_digest"].startswith("sha256:")
    assert review == {
        "unresolved_threads": 0,
        "blockers": 0,
        "critical_false_green": 0,
    }


def test_approval_does_not_claim_runtime_or_blocking_gate_completion() -> None:
    approval = load_yaml(APPROVAL_PATH)
    non_claims = approval["non_claims"]
    invariants = approval["protected_invariants"]
    status = STATUS_PATH.read_text(encoding="utf-8")

    assert all(value is False for value in non_claims.values())
    assert invariants["evaluator_leakage"] == 0
    assert invariants["ai_only_blockers"] == 0
    assert invariants["blockers_without_oracle_clause"] == 0
    assert invariants["blockers_below_E3"] == 0
    assert invariants["sensitive_profile_inference"] == 0
    assert invariants["production_personal_data_access"] == 0
    assert invariants["human_uat_replaced"] is False
    assert invariants["initial_runtime_mode"] == "SHADOW"
    assert invariants["blocking_gate_enabled"] is False
    assert "Runtime：`NOT_IMPLEMENTED`" in status
    assert "Human UAT：`REQUIRED`" in status


def test_next_state_keeps_blocking_mode_closed() -> None:
    approval = load_yaml(APPROVAL_PATH)
    next_state = approval["next_state"]

    assert next_state["spec"] == "MERGED_CLOSED_AFTER_POST_MERGE_VERIFICATION"
    assert next_state["runtime"] == "UX0_SHADOW_CONTRACTS_AND_RUNNER_NEXT"
    assert next_state["blocking_gate"] == (
        "BLOCKED_PENDING_BENCHMARK_POLICY_AND_ROLLBACK"
    )
    assert approval["rollback"] == (
        "revert_spec_approval_merge_without_runtime_data_migration"
    )
