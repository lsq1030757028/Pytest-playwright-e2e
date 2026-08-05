from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "docs/specs/ux0-synthetic-user-agent.yaml"
UX_SSOT_PATH = ROOT / "docs/ux-assurance-ssot.yaml"
ASSET_PATH = ROOT / "tests/assets/ux/ux0/canonical-contracts.yaml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_ux0_spec_is_versioned_dev3_and_shadow_first() -> None:
    spec = load_yaml(SPEC_PATH)

    assert spec["spec_id"] == "SPEC-UX0-SYNTHETIC-USER"
    assert spec["version"] == "1.0.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 29
    assert spec["scope_kind"] == "CROSS_CUTTING_M1_M3"
    assert spec["mandate_ref"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert spec["assurance"]["spec_phase"] == "DEV3"
    assert spec["assurance"]["implementation_phase"] == "DEV3"
    assert spec["assurance"]["initial_runtime_mode"] == "SHADOW"
    assert spec["assurance"][
        "blocking_promotion_requires_versioned_policy_event"
    ] is True


def test_experience_environment_is_pinned_hashable_and_synthetic_only() -> None:
    environment = load_yaml(SPEC_PATH)["experience_environment"]

    assert {
        "environment_id",
        "revision",
        "schema_version",
        "content_hash",
    } == set(environment["identity_fields"])
    assert {
        "persona_revision",
        "journey_revision",
        "requirement_revision",
        "design_system_revision",
        "code_sha",
        "fixture_revision",
        "browser_revision",
        "playwright_revision",
        "evaluator_revision",
        "capability_versions",
        "random_seed",
    } <= set(environment["required_pins"])
    assert environment["context_fields"]["account_and_data_state"][
        "synthetic_fixture_only"
    ] is True
    assert environment["context_fields"]["account_and_data_state"][
        "production_account_forbidden"
    ] is True
    assert environment["canonical_hash"]["algorithm"] == "sha256"
    assert environment["canonical_hash"]["deterministic_serialization"] is True


def test_persona_is_behavioral_and_sensitive_inference_is_forbidden() -> None:
    spec = load_yaml(SPEC_PATH)
    profile = spec["synthetic_user_profile"]
    environment = spec["experience_environment"]

    assert profile["profile_is_behavioral_not_demographic"] is True
    assert {
        "inferred_race",
        "inferred_health_condition",
        "inferred_religion",
        "inferred_sexual_orientation",
        "biometric_emotion",
    } == set(profile["forbidden_fields"])
    assert environment["sensitive_profile_rules"][
        "protected_trait_inference_forbidden"
    ] is True
    assert environment["sensitive_profile_rules"][
        "demographic_stereotyping_forbidden"
    ] is True
    assert environment["sensitive_profile_rules"]["biometric_input_forbidden"] is True


def test_experience_oracle_is_external_and_hidden_fields_do_not_reach_actor() -> None:
    spec = load_yaml(SPEC_PATH)
    oracle = spec["experience_oracle"]
    journey = spec["journey_contract"]

    assert oracle["subjective_preference_without_authority_is_oracle"] is False
    assert {
        "hidden_expected_action",
        "evaluator_scoring_key",
        "mutation_location",
        "disallowed_shortcut",
    } == set(oracle["hidden_from_actor"])
    assert "evaluator_only" in journey["actor_never_receives"]
    assert "hidden_answer_key" in journey["actor_never_receives"]
    assert "preferred_locator_sequence" in journey["actor_never_receives"]
    assert "mutation_identity" in journey["actor_never_receives"]


def test_synthetic_user_agent_is_capability_governed_and_side_effect_bounded() -> None:
    contract = load_yaml(SPEC_PATH)["agent_contract"]

    assert contract["agent_name"] == "SyntheticUserAgent"
    assert contract["execution_model"] == "governed_controller_over_capability_atoms"
    assert {
        "ux.profile.resolve",
        "ux.journey.compile",
        "ux.environment.materialize",
        "ux.execute.playwright",
        "ux.observe.interaction",
        "ux.observe.accessibility",
        "ux.evaluate.deterministic",
        "ux.evaluate.ai_proposal",
        "ux.adjudicate.evidence_gate",
        "ux.report",
        "ux.replay",
    } <= set(contract["capabilities"])
    assert contract["permission_rules"]["production_personal_data"] == "DENY"
    assert contract["permission_rules"]["secret_access"] == "DENY"
    assert contract["permission_rules"]["oracle_change"] == "DENY"
    assert contract["permission_rules"]["release_verdict_direct_write"] == "DENY"
    assert "production_write" in contract["side_effects"]["forbidden"]
    assert contract["capability_results_are_artifacts_not_campaign_mutation"] is True


def test_deterministic_observability_precedes_ai_interpretation() -> None:
    spec = load_yaml(SPEC_PATH)
    observability = spec["observability"]
    ai = spec["ai_finding_contract"]

    assert "JOURNEY_COMPLETED" in observability["interaction_events"]
    assert "JOURNEY_ABANDONED" in observability["interaction_events"]
    assert "required_feedback_latency" in observability["derived_metrics"]
    assert "keyboard_completion" in observability["derived_metrics"]
    assert "unexpected_state_loss" in observability["derived_metrics"]
    assert "inferred_emotion" in observability["forbidden_metric_claims"]
    assert ai["status"] == "CANDIDATE_ONLY"
    assert "mark_blocker" in ai["ai_may_not"]
    assert "change_oracle" in ai["ai_may_not"]
    assert "change_release_state" in ai["ai_may_not"]
    assert ai["unsupported_finding_action"] == "KEEP_NONBLOCKING_CANDIDATE"


def test_evidence_and_finding_lifecycle_prevent_ai_self_promotion() -> None:
    spec = load_yaml(SPEC_PATH)
    levels = spec["experience_evidence_levels"]
    lifecycle = spec["finding_lifecycle"]

    assert list(levels) == ["E0", "E1", "E2", "E3", "E4"]
    assert lifecycle["states"] == [
        "OBSERVED",
        "SUPPORTED",
        "REPRODUCED",
        "PROVEN",
        "CONTROLLED",
        "DISMISSED",
    ]
    assert lifecycle["promotion_rules"]["OBSERVED_to_SUPPORTED"] == (
        "evidence_level_at_least_E2"
    )
    assert lifecycle["promotion_rules"]["SUPPORTED_to_REPRODUCED"] == (
        "evidence_level_at_least_E3"
    )
    assert lifecycle["promotion_rules"]["REPRODUCED_to_PROVEN"] == (
        "evidence_level_at_least_E4"
    )
    assert lifecycle["ai_self_promotion_forbidden"] is True


def test_ux_levels_and_verdicts_are_risk_adaptive_not_mechanical() -> None:
    spec = load_yaml(SPEC_PATH)
    levels = spec["ux_assurance_levels"]
    verdict = spec["verdict_contract"]

    assert set(levels) == {"UX0", "UX1", "UX2", "UX3"}
    assert levels["UX0"]["journey_required"] is False
    assert levels["UX1"]["minimum_matrix"]["journeys"] == 1
    assert levels["UX2"]["minimum_matrix"]["recovery_paths"] == 1
    assert levels["UX3"]["minimum_matrix"]["repeated_replay"] == 3
    assert levels["UX3"]["minimum_matrix"]["adversarial_environment"] is True
    assert verdict["initial_mode"] == "SHADOW"
    assert verdict["ai_opinion_alone_blocks"] is False
    assert verdict["missing_oracle_action"] == "BLOCKED"
    assert verdict["tampered_evidence_action"] == "INVALID"
    assert verdict["blocking_rules"]["subjective_copy_or_visual_preference"][
        "blocking"
    ] is False


def test_blocking_promotion_requires_benchmark_replay_policy_and_rollback() -> None:
    rollout = load_yaml(SPEC_PATH)["rollout_policy"]

    assert rollout["phase_2"] == "SHADOW_CONTRACTS_AND_RUNNER"
    assert rollout["phase_3"] == "TODOMVC_UX_MUTATION_PROOF"
    assert {
        "false_positive_benchmark_pass",
        "false_negative_mutation_proof_pass",
        "independent_replay_pass",
        "critical_false_green_zero",
        "versioned_policy_event",
        "rollback_verified",
    } == set(rollout["blocking_promotion_prerequisites"])
    assert rollout["rollback"] == "disable_gate_preserve_historical_evidence"


def test_ux_ssot_requires_triage_and_preserves_human_uat() -> None:
    policy = load_yaml(UX_SSOT_PATH)

    assert policy["spec_ref"] == "SPEC-UX0-SYNTHETIC-USER@1.0.0"
    assert policy["required_triage"]["default_when_unknown"] == "UX2"
    assert policy["pr_gate"]["mode"] == "SHADOW_UNTIL_PROMOTED"
    assert policy["pr_gate"]["ai_finding_can_block"] is False
    assert policy["blocking_promotion"]["rollback_action"] == (
        "disable_gate_preserve_evidence"
    )
    assert policy["required_invariants"]["human_uat_replaced"] == 0
    assert policy["required_invariants"]["ai_only_blocker"] == 0


def test_canonical_assets_cover_profiles_environments_journeys_and_negative_cases() -> None:
    assets = load_yaml(ASSET_PATH)

    assert assets["spec_ref"] == "SPEC-UX0-SYNTHETIC-USER@1.0.0"
    assert {profile["profile_id"] for profile in assets["profiles"]} == {
        "ux-persona-novice",
        "ux-persona-keyboard",
        "ux-persona-interrupted",
    }
    assert {environment["environment_id"] for environment in assets["environments"]} == {
        "ux-env-desktop-normal",
        "ux-env-keyboard",
    }
    assert {journey["journey_id"] for journey in assets["journeys"]} == {
        "ux-journey-add-task",
        "ux-journey-keyboard-primary",
    }
    negative = {case["id"]: case["expected"] for case in assets["negative_cases"]}
    assert negative["UX-NEG-AI-BLOCKER"] == "KEEP_NONBLOCKING_CANDIDATE"
    assert negative["UX-NEG-EVALUATOR-LEAK"] == "INVALID"
    assert negative["UX-NEG-SENSITIVE-PERSONA"] == "REJECT"
    assert negative["UX-NEG-BLOCKING-BEFORE-BENCHMARK"] == "PROMOTION_DENIED"


def test_repository_entrypoint_and_ci_reference_ux_assurance() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    status = (ROOT / "docs/implementation-status.md").read_text(encoding="utf-8")

    assert "docs/ux-assurance-ssot.md" in agents
    assert "UX Triage" in agents
    assert "UX0 Synthetic User SPEC validation" in ci
    assert "tests/unit/test_ux0_synthetic_user_spec.py" in ci
    assert "UX0 Synthetic User" in status
    assert "SHADOW" in status
    assert "Human UAT" in status
