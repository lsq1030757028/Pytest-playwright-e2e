from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "docs/specs/repository-security-baseline.yaml"
SPEC_PATH = ROOT / "docs/specs/repository-security-baseline.md"
THREAT_MODEL_PATH = ROOT / "docs/security/repository-security-threat-model.md"
TEST_DESIGN_PATH = ROOT / "docs/testing/repository-security-baseline-test-design.md"


def load_policy() -> dict[str, object]:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def test_security_baseline_is_versioned_owner_authorized_dev3_ux0() -> None:
    policy = load_policy()

    assert policy["spec_id"] == "SPEC-REPOSITORY-SECURITY-BASELINE"
    assert policy["version"] == "0.1.0"
    assert policy["status"] == "CANDIDATE"
    assert policy["goal_issue"] == 52
    assert policy["assurance"] == {
        "dev": "DEV3",
        "ux": "UX0",
        "user_facing_effect": False,
        "human_uat_required": False,
    }
    assert policy["authority"]["type"] == "repository_owner_direct_instruction"
    assert policy["authority"]["durable_record"] == "issue_52"
    assert policy["authority"]["mandate_used_for_scope_expansion"] is False


def test_scope_excludes_secret_access_and_unsafe_external_changes() -> None:
    policy = load_policy()
    excluded = set(policy["scope"]["excluded"])

    assert {
        "codex_security",
        "real_secret_acquisition_disclosure_storage_or_rotation",
        "production_or_personal_data",
        "automatic_public_git_history_rewrite",
        "oracle_or_experience_oracle_change",
        "policy_floor_reduction",
        "permission_widening",
        "direct_main_write",
        "automatic_ruleset_or_branch_protection_change_without_permission",
        "M4_M5_M6",
    }.issubset(excluded)
    assert policy["implementation_phase"]["separate_pr_required"] is True
    assert policy["implementation_phase"]["starts_only_after_spec_merged_to_main"] is True


def test_secret_and_fork_safety_invariants_fail_closed() -> None:
    policy = load_policy()
    secret_scan = policy["secret_scan"]
    codeql = policy["codeql"]
    invariants = policy["required_invariants"]

    assert secret_scan["complete_reachable_history_required"] is True
    assert secret_scan["print_full_secret_value"] is False
    assert secret_scan["confirmed_finding_action"] == "FAIL_CLOSED"
    assert set(secret_scan["candidate_scanners"]) == {"gitleaks", "trufflehog"}
    assert codeql["immutable_action_pins_required"] is True
    assert codeql["least_privilege_permissions_required"] is True
    assert codeql["untrusted_fork_receives_repository_secrets"] is False
    assert codeql["untrusted_fork_receives_write_token"] is False
    assert invariants["real_secret_value_in_logs_or_artifacts"] == 0
    assert invariants["confirmed_secret_finding_silently_ignored"] == 0
    assert invariants["critical_false_green"] == 0


def test_security_assets_and_external_owner_boundary_are_truthful() -> None:
    policy = load_policy()
    baseline = policy["current_baseline"]
    planned_assets = set(policy["implementation_phase"]["planned_assets"])

    assert baseline["repository_visibility"] == "public"
    assert baseline["dependabot_asset_present"] == ".github/dependabot.yml"
    assert baseline["repository_secret_scanning_connector_verified"] is False
    assert {
        ".github/workflows/security-codeql.yml",
        ".github/workflows/security-secrets.yml",
        ".github/dependabot.yml",
        "SECURITY.md",
        "security_validation_tests",
    }.issubset(planned_assets)
    assert policy["deployment"]["connector_can_change_rulesets_or_branch_protection"] is False


def test_threat_model_covers_privileged_pr_and_history_failure_modes() -> None:
    threat_model = THREAT_MODEL_PATH.read_text(encoding="utf-8")

    assert "TM-REPOSITORY-SECURITY-BASELINE@0.1.0" in threat_model
    assert "Public contribution boundary" in threat_model
    assert "Workflow supply-chain boundary" in threat_model
    assert "Public-history incident boundary" in threat_model
    assert "pull_request_target" in threat_model
    assert "shallow checkout" in threat_model
    assert "rotate/revoke first" in threat_model
    assert "Codex Security is outside this Goal" in threat_model


def test_test_design_defines_detection_redaction_and_adjacent_positive_proofs() -> None:
    test_design = TEST_DESIGN_PATH.read_text(encoding="utf-8")

    assert "TD-REPOSITORY-SECURITY-BASELINE@0.1.0" in test_design
    for obligation in range(1, 13):
        assert f"SEC-{obligation:02d}" in test_design
    assert "earlier commit of an ephemeral repository" in test_design
    assert "complete canary value never appears" in test_design
    assert "adjacent positive" in test_design
    assert "Fork and token isolation" in test_design
    assert "Merge is not closure" in test_design


def test_markdown_spec_and_machine_policy_reference_the_same_contract() -> None:
    policy = load_policy()
    spec = SPEC_PATH.read_text(encoding="utf-8")
    threat_model = THREAT_MODEL_PATH.read_text(encoding="utf-8")
    test_design = TEST_DESIGN_PATH.read_text(encoding="utf-8")

    assert "SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0" in spec
    assert "Issue #52" in spec
    assert "DEV3 / UX0" in spec
    assert "Gitleaks and TruffleHog" in spec
    assert "SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0" in threat_model
    assert "SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0" in test_design
    assert policy["closure"]["spec_merge_closes_goal"] is False
