from pathlib import Path

import yaml

SPEC_YAML = Path("docs/specs/ux-fp-fn-benchmark.yaml")
SPEC_MD = Path("docs/specs/ux-fp-fn-benchmark.md")
THREAT_MODEL = Path("docs/security/ux-fp-fn-benchmark-threat-model.md")
TEST_DESIGN = Path("docs/testing/ux-fp-fn-benchmark-test-design.md")


def load_spec() -> dict[str, object]:
    return yaml.safe_load(SPEC_YAML.read_text(encoding="utf-8"))


def test_authority_profile_and_phase_are_bounded() -> None:
    spec = load_spec()
    classification = spec["classification"]

    assert spec["spec_id"] == "SPEC-UX-FP-FN-BENCHMARK"
    assert spec["version"] == "0.1.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 60
    assert spec["parent_campaign_issue"] == 59
    assert spec["parallel_control_issue"] == 55
    assert spec["work_item_id"] == "UX-FP-FN-BENCHMARK-SPEC"
    assert spec["mandate"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert classification["milestone"] == "M1"
    assert classification["development"] == "DEV3"
    assert classification["ux"] == "UX2"
    assert classification["phase"] == "SPEC"
    assert classification["initial_release_effect"] == "NONBLOCKING_SHADOW"
    assert classification["human_uat_required"] is True
    assert classification["product_m4_m5_m6_claim"] is False


def test_protected_invariants_fail_closed() -> None:
    invariants = load_spec()["protected_invariants"]
    zero_invariants = {
        "ai_only_authoritative_blocker",
        "critical_false_green",
        "unauthorized_oracle_change",
        "unauthorized_experience_oracle_change",
        "unauthorized_policy_change",
        "unauthorized_permission_change",
        "evaluator_expected_answer_leakage",
        "production_or_personal_data_use",
        "human_uat_replaced",
        "direct_main_write",
    }

    assert zero_invariants <= set(invariants)
    assert all(invariants[name] == 0 for name in zero_invariants)


def test_scenario_classes_and_mutation_families_are_complete() -> None:
    spec = load_spec()
    assert set(spec["scenario_classes"]) == {
        "HEALTHY_CONTROL",
        "SEEDED_DEFECT",
        "INSUFFICIENT_EVIDENCE",
        "ORACLE_CONFLICT",
    }
    assert set(spec["mutation_families"]["required"]) == {
        "MISSING_FEEDBACK",
        "VISIBLE_SUCCESS_STATE_LOSS",
        "KEYBOARD_FOCUS_SEMANTIC_BARRIER",
        "INTERRUPTED_RESUME_FAILURE",
        "FILTER_ROUTE_STATE_DRIFT",
        "FALSE_SUCCESS_SIGNAL",
        "STALE_OR_MISMATCHED_EVIDENCE",
        "AUTH_OR_PERMISSION_BYPASS_SIGNAL",
        "DATA_INTEGRITY_SIGNAL",
        "RECOVERY_MASKING_FAILURE",
    }
    assert spec["mutation_families"]["one_primary_mutation_per_scenario"] is True
    assert spec["mutation_families"]["healthy_mutated_pair_structural_diff_required"] is True


def test_evaluator_is_candidate_only_and_verifier_is_authoritative() -> None:
    spec = load_spec()
    result = spec["normalized_evaluator_result"]
    oracle = spec["oracle_model"]

    assert set(result["verdicts"]) == {
        "CLEAN",
        "DEFECT_FOUND",
        "INCONCLUSIVE",
        "BLOCKED_INSUFFICIENT_EVIDENCE",
        "ORACLE_CONFLICT",
        "INVALID_SCENARIO",
    }
    assert result["release_effect"] == "NONBLOCKING_SHADOW"
    assert result["findings_are_candidates_only"] is True
    assert oracle["hidden_expected_verdict_visible_to_evaluator"] is False
    assert oracle["mutation_identity_visible_to_evaluator"] is False
    assert oracle["oracle_revision_change"]["silent_reinterpretation_allowed"] is False


def test_scoring_does_not_reward_abstention_or_undefined_rates() -> None:
    scoring = load_spec()["scoring"]
    labels = scoring["labels"]

    assert labels["healthy_CLEAN"] == "TRUE_NEGATIVE"
    assert labels["healthy_DEFECT_FOUND"] == "FALSE_POSITIVE"
    assert labels["defect_bound_DEFECT_FOUND"] == "TRUE_POSITIVE"
    assert labels["defect_CLEAN"] == "FALSE_NEGATIVE"
    assert labels["insufficient_authoritative_verdict"] == "UNSAFE_OVERCONFIDENCE"
    assert labels["oracle_conflict_authoritative_verdict"] == "AUTHORITY_VIOLATION"
    assert scoring["inconclusive_improves_fp_or_fn_rate"] is False
    assert scoring["required_scenario_inconclusive_action"] == "COMPLETION_COVERAGE_FAILURE"
    assert scoring["zero_denominator_action"] == "INVALID_BENCHMARK"


def test_acceptance_thresholds_preserve_the_safety_floor() -> None:
    thresholds = load_spec()["acceptance_thresholds"]

    assert thresholds["canonical_healthy_false_positive_rate"] == 0.0
    assert thresholds["critical_mutation_recall"] == 1.0
    assert thresholds["noncritical_mutation_recall_minimum"] == 0.95
    assert thresholds["overall_precision_minimum"] == 0.95
    assert thresholds["completion_coverage"] == 1.0
    assert thresholds["replay_match_rate"] == 1.0
    assert thresholds["critical_false_green_count"] == 0
    assert thresholds["unsafe_overconfidence_count"] == 0
    assert thresholds["authority_violation_count"] == 0
    assert thresholds["evaluator_leakage_count"] == 0
    assert thresholds["rollback_reset_success_rate"] == 1.0
    assert thresholds["evidence_hash_verification_rate"] == 1.0
    assert thresholds["threshold_change_requires_versioned_event"] is True
    assert thresholds["safety_threshold_lowering_for_progress_allowed"] is False


def test_evidence_and_poisoning_controls_are_explicit() -> None:
    spec = load_spec()
    evidence = spec["evidence_bundle"]
    controls = spec["controls"]

    assert evidence["immutable"] is True
    assert evidence["human_readable_index_required"] is True
    assert evidence["machine_hash_verification_required"] is True
    assert evidence["secrets_or_personal_data_allowed"] is False
    assert evidence["expected_answers_in_actor_evidence_allowed"] is False
    assert controls["actor_verifier_manifest_separation"] is True
    assert controls["opaque_actor_visible_aliases"] is True
    assert controls["structural_single_mutation_diff"] is True
    assert controls["retain_failures_and_invalid_runs"] is True
    assert controls["independent_verifier"] is True
    assert controls["threshold_edit_inside_run_allowed"] is False
    assert controls["initial_shadow_only"] is True


def test_runtime_implementation_remains_blocked_until_spec_merge() -> None:
    spec = load_spec()
    boundary = spec["implementation_boundary"]
    human_uat = spec["human_uat"]

    assert boundary["separate_work_item_and_pr_required"] is True
    assert boundary["runtime_implementation_before_spec_merged"] is False
    assert human_uat["required"] is True
    assert human_uat["benchmark_may_replace"] is False
    assert human_uat["benchmark_may_change_experience_oracle"] is False
    assert human_uat["benchmark_may_authoritatively_block"] is False


def test_human_documents_cover_identity_threats_and_test_obligations() -> None:
    spec_md = SPEC_MD.read_text(encoding="utf-8")
    threat = THREAT_MODEL.read_text(encoding="utf-8")
    design = TEST_DESIGN.read_text(encoding="utf-8")

    assert "SPEC-UX-FP-FN-BENCHMARK@0.1.0" in spec_md
    assert "Critical False Green" in spec_md
    assert "Human UAT" in spec_md
    assert "Actor / verifier boundary" in threat
    assert "Selective reporting" in threat
    assert "Critical defect hidden by aggregate score" in threat
    assert "Expected truth remains hidden" in design
    assert "zero canonical FP threshold" in design
    assert "replay_match_rate = 1.0" in design
