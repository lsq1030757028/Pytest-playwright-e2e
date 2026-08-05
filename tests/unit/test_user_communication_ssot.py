from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "docs/user-communication-ssot.yaml"
DOCUMENT_PATH = ROOT / "docs/user-communication-ssot.md"
AGENTS_PATH = ROOT / "AGENTS.md"


def load_policy() -> dict[str, object]:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def test_user_communication_policy_is_active_and_mandatory() -> None:
    policy = load_policy()
    agents = AGENTS_PATH.read_text(encoding="utf-8")

    assert policy["name"] == "cloud-development-user-communication-ssot"
    assert policy["version"] == "1.0.0"
    assert policy["status"] == "ACTIVE"
    assert policy["goal_issue"] == 39
    assert "docs/user-communication-ssot.md" in agents
    assert "docs/user-communication-ssot.yaml" in agents
    assert DOCUMENT_PATH.is_file()


def test_business_outcome_precedes_technical_evidence() -> None:
    policy = load_policy()

    assert policy["priority_order"] == [
        "business_outcome",
        "current_delivery_status",
        "decision_relevant_facts_and_boundaries",
        "next_business_plan",
        "necessary_technical_evidence",
    ]
    assert policy["business_language"]["effect_before_implementation_detail"] is True
    assert policy["business_language"]["technical_terms_are_supporting_evidence"] is True
    assert policy["technical_evidence"]["supporting_not_primary_narrative"] is True
    assert policy["technical_evidence"][
        "full_logs_hash_lists_and_file_lists_default_to_appendix"
    ] is True


def test_status_vocabulary_prevents_premature_completion_claims() -> None:
    policy = load_policy()
    vocabulary = policy["status_vocabulary"]
    rules = policy["status_rules"]

    assert list(vocabulary) == [
        "PLANNED",
        "IMPLEMENTING",
        "IMPLEMENTED",
        "VERIFIED",
        "MERGED",
        "RELEASED",
        "CLOSED",
        "BLOCKED",
        "FAILED",
    ]
    assert rules["unqualified_done_requires"] == "CLOSED"
    assert rules["implementation_must_not_imply_verification"] is True
    assert rules["verification_must_not_imply_merge"] is True
    assert rules["merge_must_not_imply_release"] is True
    assert rules["release_must_not_imply_closed"] is True
    assert rules["partial_success_must_not_be_reported_as_total_success"] is True


def test_concision_never_hides_decision_relevant_truth() -> None:
    policy = load_policy()
    truth = policy["truth_preservation"]
    concision = policy["concision"]

    assert {
        "failed_queued_running_or_unverified_checks",
        "not_merged_not_released_or_not_closed_when_applicable",
        "blockers_residual_risks_known_limits_and_out_of_scope",
        "human_uat_human_approval_or_external_dependency",
        "uncertainty_inference_or_insufficient_evidence",
    } <= set(truth["mandatory_disclosures"])
    assert {
        "plan_reported_as_implemented",
        "branch_implementation_reported_as_merged",
        "pull_request_verification_reported_as_main_verification",
        "build_success_reported_as_production_ready",
        "failure_or_blocker_hidden_for_brevity",
        "inference_reported_as_fact",
        "long_tool_logs_used_as_default_user_report",
    } <= set(truth["prohibited"])
    assert concision["report_delta_only_in_progress_updates"] is True
    assert concision["chronological_tool_diary_prohibited"] is True
    assert concision["repeated_full_summary_prohibited"] is True


def test_default_report_is_short_business_focused_and_actionable() -> None:
    policy = load_policy()
    response = policy["response_structure"]
    plan = policy["business_language"]["plan_must_explain"]

    assert response["simple_update"]["preferred_sentence_count_min"] == 1
    assert response["simple_update"]["preferred_sentence_count_max"] == 3
    assert response["stage_or_final_report"]["maximum_default_sections"] == 4
    assert response["stage_or_final_report"]["sections"] == [
        "conclusion",
        "implemented_business_capability",
        "facts_and_boundaries",
        "next_plan",
    ]
    assert plan == ["next_business_action", "purpose", "completion_standard"]


def test_communication_policy_does_not_relax_delivery_governance() -> None:
    boundaries = load_policy()["protected_boundaries"]

    assert boundaries == {
        "changes_oracle": False,
        "changes_permission": False,
        "changes_release_gate": False,
        "changes_safety_floor": False,
        "changes_autonomous_mandate_scope": False,
    }
