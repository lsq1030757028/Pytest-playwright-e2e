from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANDATE_PATH = ROOT / "docs/specs/autonomous-execution-mandate.yaml"
SSOT_PATH = ROOT / "docs/github-development-ssot.yaml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_mandate_is_active_versioned_and_owner_authorized() -> None:
    mandate = load_yaml(MANDATE_PATH)

    assert mandate["mandate_id"] == "MANDATE-AUTONOMY-M1-M3"
    assert mandate["version"] == "1.0.0"
    assert mandate["status"] == "ACTIVE"
    assert mandate["authority"]["type"] == "repository_owner_instruction"
    assert mandate["authority"]["issue"] == 23
    assert "不需要人类批准" in mandate["authority"]["statement"]


def test_mandate_scope_is_bounded_to_m1_m2_m3_and_dev0_to_dev3() -> None:
    mandate = load_yaml(MANDATE_PATH)

    assert mandate["scope"]["milestones"] == ["M1", "M2", "M3"]
    assert mandate["scope"]["profiles"] == ["DEV0", "DEV1", "DEV2", "DEV3"]
    assert "DEV-E" not in mandate["scope"]["profiles"]
    assert "M1.0_memory_benchmark_harness" in mandate["scope"]["includes"]


def test_autonomous_dev3_keeps_spec_evidence_review_and_release_gates() -> None:
    mandate = load_yaml(MANDATE_PATH)
    preconditions = mandate["preconditions"]

    assert preconditions["approved_goal_required"] is True
    assert preconditions["approved_spec_required_when_applicable"] is True
    assert preconditions["mandate_reference_in_dev3_pr_required"] is True
    assert preconditions["threat_model_required_for_dev3"] is True
    assert preconditions["rollback_or_recovery_required"] is True
    assert preconditions["required_checks_green"] is True
    assert preconditions["unresolved_review_threads"] == 0
    assert preconditions["blockers"] == 0
    assert preconditions["critical_false_green"] == 0
    assert preconditions["post_merge_main_release_cleanup_required"] is True


def test_external_irreversible_and_sensitive_boundaries_remain_blocked() -> None:
    mandate = load_yaml(MANDATE_PATH)
    excluded = set(mandate["out_of_mandate"])

    assert {
        "real_production_data_write",
        "personal_data_exposure",
        "secret_acquisition_or_disclosure",
        "destructive_production_migration",
        "irreversible_external_write",
        "material_irreversible_spend",
        "dangerous_real_device_action_without_bounded_device_spec",
        "higher_authority_or_oracle_conflict",
        "dev_e_production_action",
    }.issubset(excluded)
    assert mandate["out_of_mandate_action"] == "BLOCKED"
    assert mandate["scope_expansion_action"] == "REPLAN_REQUIRED"


def test_revocation_stops_new_autonomous_merges_without_erasing_history() -> None:
    mandate = load_yaml(MANDATE_PATH)
    revocation = mandate["revocation"]

    assert revocation["supported"] is True
    assert revocation["requires_versioned_change_event"] is True
    assert revocation["prevents_new_autonomous_merges"] is True
    assert revocation["preserves_historical_evidence"] is True


def test_ssot_and_templates_reference_standing_mandate_authorization() -> None:
    policy = load_yaml(SSOT_PATH)
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    pr_template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    issue_template = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE/goal.yml").read_text(encoding="utf-8")
    )
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert policy["active_autonomous_mandate"]["id"] == "MANDATE-AUTONOMY-M1-M3"
    assert policy["assurance_profiles"]["DEV3"]["authorization_mode"] == (
        "standing_mandate_or_explicit_human_approval"
    )
    assert "DEV3" in policy["agent_autonomy"]["may_auto_merge_profiles"]
    assert "active_mandate_covers_goal_profile_and_spec_when_dev3" in (
        policy["agent_autonomy"]["auto_merge_conditions"]
    )
    assert "MANDATE-AUTONOMY-M1-M3" in agents
    assert "Autonomy mandate" in pr_template
    assert any(item.get("id") == "autonomy_mandate" for item in issue_template["body"])
    assert "Autonomous execution mandate validation" in ci


def test_mandate_does_not_claim_m1_gate_completion() -> None:
    status = (ROOT / "docs/implementation-status.md").read_text(encoding="utf-8")

    assert "M1.0 SPEC" in status
    assert "M1.0 Benchmark Harness" in status
    assert "IMPLEMENTED / EVIDENCE_PENDING" in status
    assert "M1 Memory Gate：0 / 1" in status
    assert "Stage Delivery：NOT_READY" in status
