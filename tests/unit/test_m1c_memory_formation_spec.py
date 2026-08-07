from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_MD = ROOT / "docs/specs/m1c-memory-formation-spec.md"
SPEC_YAML = ROOT / "docs/specs/m1c-memory-formation.yaml"
THREAT_MD = ROOT / "docs/security/m1c-memory-formation-threat-model.md"
TEST_DESIGN_MD = ROOT / "docs/testing/m1c-memory-formation-test-design.md"


def load_spec() -> dict:
    return yaml.safe_load(SPEC_YAML.read_text(encoding="utf-8"))


def test_identity_authority_and_spec_only_boundary() -> None:
    spec = load_spec()

    assert spec["spec_id"] == "SPEC-M1C-MEMORY-FORMATION"
    assert spec["version"] == "0.1.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 74
    assert spec["parent_campaign_issue"] == 59
    assert spec["assurance"] == {"development": "DEV3", "ux": "UX0"}
    assert spec["product_claim"] == "SPEC_ONLY"

    authority = spec["authority"]
    assert authority["m1a_spec"] == "SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0"
    assert authority["m1b_spec"] == "SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL@0.1.0"
    assert authority["m1b_goal_issue"] == 69
    assert authority["m1b_status"] == "CLOSED"
    assert authority["m1b_main_merge"] == "9600ed4924ddb8b8f76322f8547c4864e71b3e67"
    assert authority["m1_benchmark_spec"] == "SPEC-M1.0-MEMORY-BENCHMARK@1.0.0"

    gate = spec["implementation_gate"]
    assert gate["implementation_allowed_after_spec_merge"] is True
    assert gate["spec_pr_runtime_implementation_forbidden"] is True
    assert gate["m1d_shared_governance_out_of_scope"] is True
    assert gate["m1e_promotion_out_of_scope"] is True


def test_explicit_formation_and_candidate_only_are_hard_invariants() -> None:
    invariants = load_spec()["core_invariants"]

    assert invariants["implicit_session_to_memory_write"] is False
    assert invariants["source_data_is_control"] is False
    assert invariants["candidate_only_formation"] is True
    assert invariants["direct_verified_output"] is False
    assert invariants["direct_promoted_output"] is False
    assert invariants["model_confidence_is_authority"] is False
    assert invariants["requirement_oracle_policy_permission_mutation"] is False
    assert invariants["exact_namespace_before_proposal"] is True
    assert invariants["provenance_before_store_write"] is True
    assert invariants["m1b_store_cas_and_authenticated_idempotency_required"] is True

    lifecycle = load_spec()["candidate_lifecycle"]
    assert lifecycle["initial_state"] == "CANDIDATE"
    assert lifecycle["initial_candidate_percent_required"] == 100
    assert lifecycle["allowed_immediate_safety_states"] == [
        "CANDIDATE",
        "CONFLICTING",
        "QUARANTINED",
    ]
    assert lifecycle["forbidden_direct_states"] == ["VERIFIED", "PROMOTED"]


def test_hot_and_background_formation_are_bounded() -> None:
    modes = load_spec()["formation_modes"]
    hot = modes["HOT_PATH"]
    background = modes["BACKGROUND_CONSOLIDATION"]

    assert hot == {
        "purpose": "current_completed_run_or_bounded_checkpoint",
        "source_ref_limit": 16,
        "source_memory_ref_limit": 16,
        "proposal_limit": 8,
        "accepted_candidate_limit": 4,
        "token_limit": 4000,
        "latency_budget_ms": 1000,
        "maximum_derivation_depth": 1,
        "unrestricted_history_scan": False,
        "automatic_shared_scope_write": False,
    }
    assert background["source_ref_limit"] == 32
    assert background["source_memory_ref_limit"] == 128
    assert background["proposal_limit"] == 32
    assert background["accepted_candidate_limit"] == 16
    assert background["token_limit"] == 16000
    assert background["latency_budget_ms"] == 10000
    assert background["maximum_derivation_depth"] == 2
    assert background["unrestricted_history_scan"] is False
    assert background["source_memory_requires_m1b_authority"] is True
    assert background["automatic_shared_scope_write"] is False


def test_source_and_request_contract_fail_closed() -> None:
    spec = load_spec()

    assert set(spec["source_classes"]) == {
        "RUN_EVENT",
        "TOOL_RESULT",
        "ARTIFACT",
        "REQUIREMENT_REVISION",
        "CODE_REVISION",
        "ENVIRONMENT_REVISION",
        "MEMORY_REVISION",
        "HUMAN_ASSERTION",
    }
    source = spec["source_contract"]
    assert source["immutable_ref_required"] is True
    assert source["canonical_hash_required"] is True
    assert source["evaluator_only_source_forbidden"] is True
    assert source["hidden_holdout_source_forbidden"] is True
    assert source["secret_acquisition_forbidden"] is True
    assert source["prompt_instructions_are_data_only"] is True
    assert source["cross_namespace_source_requires_explicit_authority"] is True

    request = spec["formation_request"]
    required = set(request["required_fields"])
    assert {
        "actor_context",
        "target_namespace",
        "source_descriptors",
        "evidence_refs",
        "authority_refs",
        "formation_rule_ref",
        "validator_profile_ref",
        "idempotency_key",
    } <= required
    forbidden = set(request["forbidden_fields"])
    assert {
        "wildcard_cross_project_namespace",
        "lifecycle_verified_override",
        "lifecycle_promoted_override",
        "model_declared_permission",
        "hidden_benchmark_answer",
        "evaluator_only_payload",
        "secret_acquisition_request",
        "automatic_shared_scope_expansion",
    } <= forbidden


def test_validation_order_keeps_authority_before_provider_and_store() -> None:
    pipeline = load_spec()["validation_pipeline"]
    order = pipeline["order"]

    assert order.index("resolve_exact_target_namespace") < order.index(
        "validate_memory_kind_schema"
    )
    assert order.index("evaluate_append_authority") < order.index(
        "reject_unsupported_or_fabricated_claims"
    )
    assert order.index("validate_evidence_bindings") < order.index(
        "resolve_duplicate_or_conflict_identity"
    )
    assert order.index("validate_current_authority_dominance") < order.index(
        "append_through_m1b_store"
    )
    assert order[-2:] == ["append_through_m1b_store", "record_replay_evidence"]
    assert pipeline["relevance_before_authority"] is False
    assert pipeline["provider_output_is_untrusted"] is True
    assert pipeline["deterministic_validator_owns_admission"] is True


def test_memory_kind_policy_does_not_preempt_m1e() -> None:
    policy = load_spec()["memory_kind_policy"]

    assert policy["WORKING"]["ttl_required"] is True
    assert policy["EPISODIC"]["allowed"] is True
    assert policy["SEMANTIC"]["factual_elements_require_source_trace"] is True
    assert policy["PROCEDURAL"]["allowed"] == "PROPOSAL_CANDIDATE_ONLY"
    assert policy["PROCEDURAL"]["arbitrary_executable_payload_forbidden"] is True
    assert policy["PROCEDURAL"]["promotion_owner"] == "M1E"
    assert policy["SKILL"]["allowed"] == "PROPOSAL_CANDIDATE_ONLY"
    assert policy["SKILL"]["permission_expansion_forbidden"] is True
    assert policy["SKILL"]["promotion_owner"] == "M1E"


def test_provenance_idempotency_duplicate_and_conflict_are_replayable() -> None:
    spec = load_spec()
    provenance = spec["formation_provenance"]
    assert {
        "ordered_source_refs",
        "source_content_hashes",
        "evidence_refs",
        "actor_principal_ref",
        "formation_rule_ref",
        "validator_profile_ref",
        "request_digest",
        "decision_digest",
    } <= set(provenance["required"])
    assert provenance["fabricated_or_unresolved_source_result"] == "REJECTED"
    assert provenance["fabricated_or_unresolved_evidence_result"] == "REJECTED"

    idempotency = spec["idempotency"]
    assert {
        "actor_principal_id",
        "target_namespace",
        "ordered_source_hashes",
        "formation_rule_ref",
        "candidate_payload_digest",
    } <= set(idempotency["authenticated_binding_fields"])
    assert idempotency["same_request_result"] == "ORIGINAL_RESULT"
    assert idempotency["rebound_key_result"] == "REJECTED"

    duplicate = spec["duplicate_and_conflict"]
    assert duplicate["exact_duplicate_fingerprint_after_authorization"] is True
    assert duplicate["duplicate_result"] == "DUPLICATE_SUPPRESSED"
    assert duplicate["same_subject_different_canonical_claim_result"] == (
        "CONFLICT_REQUIRES_REVIEW"
    )
    assert duplicate["model_confidence_may_choose_conflict_winner"] is False
    assert duplicate["silent_conflict_merge"] is False


def test_poisoning_and_replay_contract_cover_critical_paths() -> None:
    spec = load_spec()
    poisoning = spec["poisoning_controls"]
    families = set(poisoning["critical_families"])
    assert {
        "prompt_injection_as_control",
        "fabricated_source_or_evidence_id",
        "hidden_benchmark_or_evaluator_contamination",
        "cross_namespace_source_mix",
        "stale_requirement_as_current",
        "unsupported_assumption_as_fact",
        "arbitrary_executable_payload",
        "candidate_flood",
        "recursive_poison_amplification",
    } <= families
    assert poisoning["autonomous_lifecycle_promotion"] is False

    replay = spec["replay_evidence"]
    assert replay["chain_of_thought_forbidden"] is True
    assert replay["hidden_benchmark_content_forbidden"] is True
    assert replay["unauthorized_raw_content_forbidden"] is True
    assert replay["deterministic_equivalence_percent"] == 100
    assert replay["minimum_deterministic_repetitions"] == 3


def test_acceptance_thresholds_are_fail_closed() -> None:
    thresholds = load_spec()["acceptance_thresholds"]

    zero_keys = {
        "implicit_session_to_durable_memory_writes",
        "unauthorized_cross_namespace_formation_count",
        "unsupported_or_fabricated_provenance_accepted_count",
        "hidden_evaluator_contamination_accepted_count",
        "oracle_policy_permission_mutation_count",
        "unauthorized_executable_payload_accepted_count",
        "critical_poisoning_mutation_survivors",
        "m1b_critical_safety_regression_count",
    }
    assert all(thresholds[key] == 0 for key in zero_keys)
    assert thresholds["initial_candidate_state_percent"] == 100
    assert thresholds["deterministic_replay_equivalence_percent"] == 100
    assert thresholds["authenticated_idempotency_equivalence_percent"] == 100
    assert thresholds["critical_fact_extraction_recall_percent"] == 100
    assert thresholds["noncritical_candidate_precision_percent_minimum"] == 90
    assert thresholds["duplicate_suppression_determinism_percent"] == 100
    assert thresholds["conflict_surfacing_determinism_percent"] == 100
    assert thresholds["hot_formation_p95_ms_maximum"] == 1000


def test_threat_and_test_design_cover_critical_mutations() -> None:
    threat = THREAT_MD.read_text(encoding="utf-8")
    test_design = TEST_DESIGN_MD.read_text(encoding="utf-8")
    spec_md = SPEC_MD.read_text(encoding="utf-8")

    for number in range(1, 37):
        assert f"M1C-T{number:02d}" in threat

    required_phrases = (
        "prompt injection",
        "fabricated",
        "cross-project",
        "stale Requirement",
        "hidden benchmark",
        "executable",
        "candidate flood",
        "derivation-depth",
        "Forgotten",
        "100 coordinated races",
        "Deterministic replay equivalence",
    )
    combined = "\n".join((spec_md, threat, test_design))
    for phrase in required_phrases:
        assert phrase.lower() in combined.lower()


def test_spec_exit_gate_is_complete() -> None:
    acceptance = load_spec()["acceptance"]
    assert acceptance == {
        "dedicated_spec_gate_green": True,
        "full_ci_green": True,
        "secret_scan_green": True,
        "codeql_green": True,
        "review_threads": 0,
        "blockers": 0,
        "final_diff_spec_only": True,
    }
