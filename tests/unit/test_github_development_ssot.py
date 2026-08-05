from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "docs/github-development-ssot.yaml"


def load_policy() -> dict[str, object]:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def test_repository_has_one_active_github_development_ssot() -> None:
    policy = load_policy()

    assert policy["status"] == "ACTIVE"
    assert policy["source_of_truth"]["cloud_first"] is True
    assert policy["source_of_truth"]["authoritative_code_branch"] == "main"
    assert policy["source_of_truth"]["authoritative_verification"] == "github_actions"
    assert policy["source_of_truth"]["direct_main_write_allowed"] is False

    required_paths = {
        "AGENTS.md",
        "docs/github-development-ssot.md",
        "docs/github-development-ssot.yaml",
        "docs/testing/github-development-ssot-test-design.md",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/goal.yml",
    }
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path


def test_assurance_profiles_are_risk_adaptive_not_mechanical() -> None:
    profiles = load_policy()["assurance_profiles"]

    assert list(profiles) == ["DEV0", "DEV1", "DEV2", "DEV3", "DEV-E"]
    assert profiles["DEV0"]["unit_test_required_by_default"] is False
    assert profiles["DEV0"]["integration_test_required_by_default"] is False
    assert profiles["DEV1"]["unit_test_required_by_default"] is True
    assert profiles["DEV1"]["integration_test_required_by_default"] is False
    assert profiles["DEV2"]["boundary_integration_required_when_boundary_touched"] is True
    assert profiles["DEV2"]["skipped_evidence_requires_reason"] is True
    assert profiles["DEV3"]["human_approval_required"] is True
    assert profiles["DEV3"]["agent_may_downgrade"] is False
    assert profiles["DEV-E"]["evidence_backfill_required"] is True


def test_change_specific_evidence_is_separate_from_repository_regression() -> None:
    evidence = load_policy()["evidence_model"]

    assert evidence["test_obligation_required_for_nontrivial_changes"] is True
    assert evidence["change_specific_evidence"]["dynamically_selected"] is True
    assert evidence["repository_regression_gate"]["current_strategy"] == (
        "full_github_actions_baseline"
    )
    assert "explain_selected_and_skipped_layers" in evidence["selection_rules"]
    assert "do_not_mock_the_truth_boundary" in evidence["selection_rules"]


def test_agent_autonomy_has_explicit_safety_boundaries() -> None:
    policy = load_policy()
    autonomy = policy["agent_autonomy"]
    invariants = policy["required_invariants"]

    assert autonomy["may_auto_merge_profiles"] == ["DEV0", "DEV1", "DEV2"]
    assert "DEV3" in autonomy["explicit_human_approval_required_for"]
    assert "oracle_policy_permission_or_assurance_floor" in (
        autonomy["explicit_human_approval_required_for"]
    )
    assert "memory_prompt_procedure_skill_or_capability_promotion" in (
        autonomy["explicit_human_approval_required_for"]
    )
    assert "direct_main_push" in autonomy["prohibited"]
    assert "silent_oracle_change" in autonomy["prohibited"]
    assert invariants["critical_false_green"] == 0
    assert invariants["direct_main_write"] == 0


def test_lifecycle_requires_main_and_release_verification_before_close() -> None:
    policy = load_policy()
    lifecycle = policy["lifecycle"]
    release = policy["release_policy"]
    done = policy["closure"]["definition_of_done"]

    assert lifecycle["normal_path"][-3:] == ["MERGED", "RELEASE_VERIFYING", "CLOSED"]
    assert release["main_push_verification_required"] is True
    assert release["release_failure_prevents_closed_status"] is True
    assert "main_and_release_verified" in done
    assert "temporary_state_cleaned" in done


def test_github_templates_and_ci_expose_the_ssot_process() -> None:
    issue_form = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE/goal.yml").read_text(encoding="utf-8")
    )
    pr_template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert issue_form["description"]
    assert any(item.get("id") == "risk_signals" for item in issue_form["body"])
    assert "Test and evidence selection" in pr_template
    assert "Intentionally skipped" in pr_template
    assert "Auto-merge eligibility" in pr_template
    assert "Development SSOT validation" in ci_workflow
    assert "tests/unit/test_github_development_ssot.py" in ci_workflow


def test_ssot_changes_cannot_relax_governance_silently() -> None:
    self_policy = load_policy()["self_change_policy"]

    assert self_policy["minimum_profile"] == "DEV2"
    assert set(self_policy["dev3_when_relaxing"]) == {
        "safety_boundary",
        "auto_merge",
        "oracle",
        "policy",
        "permission",
        "production_approval",
    }
    assert "tests/unit/test_github_development_ssot.py" in (
        self_policy["required_consistency_files"]
    )
