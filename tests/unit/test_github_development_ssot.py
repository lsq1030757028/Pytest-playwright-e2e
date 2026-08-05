from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "docs/github-development-ssot.yaml"


def load_policy() -> dict[str, object]:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def test_repository_has_one_active_github_development_ssot() -> None:
    policy = load_policy()

    assert policy["status"] == "ACTIVE"
    assert policy["version"] == 1.2
    assert policy["source_of_truth"]["cloud_first"] is True
    assert policy["source_of_truth"]["authoritative_code_branch"] == "main"
    assert policy["source_of_truth"]["authoritative_verification"] == "github_actions"
    assert policy["source_of_truth"]["direct_main_write_allowed"] is False

    required_paths = {
        "AGENTS.md",
        "docs/github-development-ssot.md",
        "docs/github-development-ssot.yaml",
        "docs/specs/autonomous-execution-mandate-spec.md",
        "docs/specs/autonomous-execution-mandate.yaml",
        "docs/testing/github-development-ssot-test-design.md",
        "docs/testing/autonomous-execution-mandate-test-design.md",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/goal.yml",
    }
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path


def test_spec_gate_precedes_runtime_implementation() -> None:
    policy = load_policy()
    lifecycle = policy["lifecycle"]
    spec_gate = policy["spec_gate"]
    planning = policy["planning"]
    autonomy = policy["agent_autonomy"]
    invariants = policy["required_invariants"]

    expected_prefix = [
        "PROPOSED",
        "TRIAGED",
        "SPEC_DRAFT",
        "SPEC_IN_REVIEW",
        "SPEC_APPROVED",
        "PLANNED",
        "IMPLEMENTING",
    ]
    assert lifecycle["normal_path"][:7] == expected_prefix
    assert "OUT_OF_MANDATE" in lifecycle["states"]
    assert spec_gate["implementation_may_start_only_after_spec_merged_to_main"] is True
    assert spec_gate["separate_spec_and_implementation_pr_by_default"] is True
    assert spec_gate["spec_completion_does_not_complete_module"] is True
    assert spec_gate["exceptions"]["DEV0"]["lightweight_inline_spec_allowed"] is True
    assert spec_gate["exceptions"]["DEV-E"]["emergency_spec_required_before_action"] is True
    assert planning["spec_before_runtime_implementation"] is True
    assert "runtime_implementation_before_required_spec_merged" in autonomy["prohibited"]
    assert invariants["runtime_implementation_without_approved_spec"] == 0
    assert invariants["silent_spec_semantic_overwrite"] == 0


def test_assurance_profiles_are_risk_adaptive_not_mechanical() -> None:
    profiles = load_policy()["assurance_profiles"]

    assert list(profiles) == ["DEV0", "DEV1", "DEV2", "DEV3", "DEV-E"]
    assert profiles["DEV0"]["unit_test_required_by_default"] is False
    assert profiles["DEV0"]["integration_test_required_by_default"] is False
    assert profiles["DEV1"]["unit_test_required_by_default"] is True
    assert profiles["DEV1"]["integration_test_required_by_default"] is False
    assert profiles["DEV2"]["approved_spec_required"] is True
    assert profiles["DEV2"]["boundary_integration_required_when_boundary_touched"] is True
    assert profiles["DEV2"]["skipped_evidence_requires_reason"] is True
    assert profiles["DEV3"]["approved_spec_required"] is True
    assert profiles["DEV3"]["authorization_mode"] == (
        "standing_mandate_or_explicit_human_approval"
    )
    assert profiles["DEV3"][
        "repeated_human_approval_required_when_active_mandate_covers_change"
    ] is False
    assert profiles["DEV3"]["agent_may_downgrade"] is False
    assert profiles["DEV-E"]["emergency_spec_required"] is True
    assert profiles["DEV-E"]["standing_mandate_covers"] is False


def test_change_specific_evidence_is_separate_from_repository_regression() -> None:
    evidence = load_policy()["evidence_model"]

    assert evidence["test_obligation_required_for_nontrivial_changes"] is True
    assert evidence["change_specific_evidence"]["dynamically_selected"] is True
    assert evidence["repository_regression_gate"]["current_strategy"] == (
        "full_github_actions_baseline"
    )
    assert "explain_selected_and_skipped_layers" in evidence["selection_rules"]
    assert "do_not_mock_the_truth_boundary" in evidence["selection_rules"]


def test_agent_autonomy_has_bounded_dev3_authority() -> None:
    policy = load_policy()
    autonomy = policy["agent_autonomy"]
    mandate = policy["active_autonomous_mandate"]
    invariants = policy["required_invariants"]

    assert mandate["id"] == "MANDATE-AUTONOMY-M1-M3"
    assert mandate["status"] == "ACTIVE"
    assert mandate["scope_milestones"] == ["M1", "M2", "M3"]
    assert mandate["covered_profiles"] == ["DEV0", "DEV1", "DEV2", "DEV3"]
    assert mandate["dev_e_covered"] is False
    assert autonomy["may_auto_merge_profiles"] == ["DEV0", "DEV1", "DEV2", "DEV3"]
    assert "active_mandate_covers_goal_profile_and_spec_when_dev3" in (
        autonomy["auto_merge_conditions"]
    )
    assert "dev3_not_covered_by_active_mandate" in (
        autonomy["explicit_human_approval_required_for"]
    )
    assert "out_of_mandate_external_action" in autonomy["prohibited"]
    assert "direct_main_push" in autonomy["prohibited"]
    assert "silent_spec_semantic_overwrite" in autonomy["prohibited"]
    assert "silent_oracle_change" in autonomy["prohibited"]
    assert invariants["critical_false_green"] == 0
    assert invariants["direct_main_write"] == 0
    assert invariants["out_of_mandate_action_executed"] == 0


def test_lifecycle_requires_main_and_release_verification_before_close() -> None:
    policy = load_policy()
    lifecycle = policy["lifecycle"]
    release = policy["release_policy"]
    done = policy["closure"]["definition_of_done"]

    assert lifecycle["normal_path"][-3:] == ["MERGED", "RELEASE_VERIFYING", "CLOSED"]
    assert release["main_push_verification_required"] is True
    assert release["release_failure_prevents_closed_status"] is True
    assert "scope_and_mandate_coverage_confirmed" in done
    assert "required_spec_approved_and_merged" in done
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
    assert any(item.get("id") == "autonomy_mandate" for item in issue_form["body"])
    assert "SPEC reference and phase" in pr_template
    assert "Autonomy mandate" in pr_template
    assert "Implementation did not start before" in pr_template
    assert "Test and evidence selection" in pr_template
    assert "Intentionally skipped" in pr_template
    assert "Auto-merge eligibility" in pr_template
    assert "Development SSOT validation" in ci_workflow
    assert "Autonomous execution mandate validation" in ci_workflow
    assert "tests/unit/test_github_development_ssot.py" in ci_workflow
    assert "tests/unit/test_autonomous_execution_mandate.py" in ci_workflow


def test_ssot_changes_cannot_relax_governance_silently() -> None:
    self_policy = load_policy()["self_change_policy"]

    assert self_policy["minimum_profile"] == "DEV2"
    assert set(self_policy["dev3_when_relaxing"]) == {
        "spec_gate",
        "safety_boundary",
        "auto_merge",
        "oracle",
        "policy",
        "permission",
        "production_approval",
        "mandate_scope",
    }
    assert self_policy["owner_authorization_for_current_change"]["issue"] == 23
    assert "tests/unit/test_github_development_ssot.py" in (
        self_policy["required_consistency_files"]
    )
    assert "tests/unit/test_autonomous_execution_mandate.py" in (
        self_policy["required_consistency_files"]
    )
