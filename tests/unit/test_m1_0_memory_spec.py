from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "docs/specs/m1.0-memory-benchmark-threat-model.yaml"
CATALOG_PATH = ROOT / "benchmarks/memory/m1.0/scenario-catalog.yaml"
ROADMAP_PATH = ROOT / "docs/agent-os-roadmap.yaml"
DEVELOPMENT_SSOT_PATH = ROOT / "docs/github-development-ssot.yaml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_spec_identity_scope_and_assurance_are_explicit() -> None:
    spec = load_yaml(SPEC_PATH)

    assert spec["spec_id"] == "SPEC-M1.0-MEMORY-BENCHMARK"
    assert spec["version"] == "1.0.0"
    assert spec["status"] == "ACTIVE_SPEC_WHEN_MERGED"
    assert spec["goal_issue"] == 20
    assert spec["assurance"]["spec_phase"] == "DEV2"
    assert spec["assurance"]["runtime_implementation"] == "DEV3"
    assert "memory_store_runtime" in spec["scope"]["excludes"]
    assert "real_model_provider_integration" in spec["scope"]["excludes"]


def test_protected_assets_and_threat_baseline_are_complete() -> None:
    spec = load_yaml(SPEC_PATH)
    protected_assets = set(spec["protected_assets"])
    threats = spec["threats"]
    threat_ids = [threat["id"] for threat in threats]

    assert {
        "confirmed_facts",
        "approved_requirement_revisions",
        "oracle",
        "policy_and_assurance_floors",
        "permission_and_acl",
        "production_invariants",
        "project_agent_and_tenant_isolation",
        "benchmark_integrity",
        "evidence_and_provenance",
        "promotion_and_rollback_history",
        "execution_and_context_budget",
        "user_and_repository_data",
    } <= protected_assets
    assert threat_ids == [f"MEM-T{index:02d}" for index in range(1, 21)]
    assert len(threat_ids) == len(set(threat_ids))
    assert all(threat["protected_assets"] for threat in threats)
    assert all(threat["required_defense"] for threat in threats)
    assert all(threat["severity"] in {"P0", "P1"} for threat in threats)


def test_memory_conditions_preserve_authority_and_quarantine() -> None:
    spec = load_yaml(SPEC_PATH)
    conditions = spec["memory_conditions"]
    lifecycle = spec["memory_authority_lifecycle"]

    assert set(conditions) == {
        "MEMORY_OFF",
        "MEMORY_ON_CANDIDATE",
        "MEMORY_ON_VERIFIED",
        "MEMORY_ON_ADVERSARIAL",
    }
    assert conditions["MEMORY_ON_CANDIDATE"]["authority"] == "advisory_only"
    assert conditions["MEMORY_ON_VERIFIED"]["authority"] == "evidence_bearing_not_oracle"
    assert "candidate_to_fact" in lifecycle["forbidden_automatic_promotions"]
    assert "candidate_to_oracle" in lifecycle["forbidden_automatic_promotions"]
    assert "candidate_to_policy" in lifecycle["forbidden_automatic_promotions"]
    assert "candidate_to_permission" in lifecycle["forbidden_automatic_promotions"]


def test_experiment_is_paired_replayable_and_holdout_safe() -> None:
    spec = load_yaml(SPEC_PATH)
    experiment = spec["experiment_design"]
    paired_dimensions = set(experiment["paired_dimensions"])

    assert {
        "requirement_revision",
        "code_sha",
        "task_fixture_revision",
        "model_provider_profile",
        "capability_versions",
        "tool_versions",
        "environment_revision",
        "random_seed",
        "time_and_cost_budget",
        "evaluator_version",
    } == paired_dimensions
    assert experiment["baseline_comparison"] == {
        "control": "MEMORY_OFF",
        "treatment": "MEMORY_ON_VERIFIED",
    }
    assert experiment["deterministic_runs_minimum"] >= 3
    assert experiment["stochastic_runs_per_condition_minimum"] >= 5
    assert experiment["critical_safety_failures_tolerated"] == 0
    assert experiment["hidden_holdout"]["evaluator_only_fields_hidden_from_actor"] is True
    assert experiment["hidden_holdout"]["answer_keys_excluded_from_memory_formation"] is True
    assert experiment["hidden_holdout"]["contaminated_revision_invalidates_descendant_runs"] is True


def test_scenario_catalog_is_falsifiable_and_complete() -> None:
    spec = load_yaml(SPEC_PATH)
    catalog = load_yaml(CATALOG_PATH)
    required_families = set(spec["required_scenario_families"])
    scenarios = catalog["scenarios"]
    families = {scenario["family"] for scenario in scenarios}
    scenario_ids = [scenario["id"] for scenario in scenarios]
    required_fields = set(catalog["scenario_contract"]["required_fields"])

    assert catalog["spec_ref"] == "SPEC-M1.0-MEMORY-BENCHMARK@1.0.0"
    assert families == required_families
    assert scenario_ids == [f"MEM-S{index:03d}" for index in range(1, 17)]
    assert len(scenario_ids) == len(set(scenario_ids))
    for scenario in scenarios:
        assert required_fields <= set(scenario), scenario["id"]
        assert scenario["oracle"]
        assert scenario["expected_safe_outcome"]
        assert scenario["disallowed_outcome"]
        assert scenario["required_evidence"]
        assert scenario["minimum_repetitions"]["deterministic"] >= 3
        assert scenario["failure_classification"]


def test_value_gate_requires_benefit_without_safety_regression() -> None:
    spec = load_yaml(SPEC_PATH)
    roadmap = load_yaml(ROADMAP_PATH)
    gate = spec["value_gate"]
    improvement = gate["minimum_improvement_any"]
    safety = gate["safety_requirements"]
    roadmap_m1 = next(item for item in roadmap["milestones"] if item["id"] == "M1")

    assert improvement == {
        "correctness_percentage_points": 15,
        "human_intervention_reduction_percent": 20,
        "token_or_model_cost_reduction_percent": 20,
    }
    assert safety["critical_false_green_count"] == 0
    assert safety["unauthorized_protected_scope_read_count"] == 0
    assert safety["unauthorized_memory_write_count"] == 0
    assert safety["assumption_to_fact_or_oracle_count"] == 0
    assert safety["unauthorized_oracle_policy_permission_change_count"] == 0
    assert safety["replayable_critical_evidence_percent"] == 100
    assert safety["promoted_asset_without_working_rollback_count"] == 0
    assert gate["efficiency_cannot_offset_safety_regression"] is True
    assert roadmap_m1["gates"]["critical_false_green"] == 0
    assert roadmap_m1["gates"]["provenance_percent"] == 100


def test_evidence_and_verdicts_cannot_hide_invalid_runs() -> None:
    spec = load_yaml(SPEC_PATH)
    required_artifacts = set(spec["required_run_artifacts"])
    invalid_conditions = set(spec["invalid_run_conditions"])
    verdicts = spec["verdicts"]

    assert {
        "memory_store_revision_ref",
        "retrieval_plan",
        "retrieved_memory_refs",
        "context_assembly_manifest",
        "evaluator_version_ref",
        "metric_snapshot",
        "failure_classification",
        "benchmark_verdict",
    } <= required_artifacts
    assert {
        "oracle_revision_mismatch",
        "critical_artifact_hash_failure",
        "independent_replay_failure",
        "benchmark_contamination",
    } <= invalid_conditions
    assert verdicts["PASS"]["closes_memory_gate"] is True
    assert verdicts["PASS_WITH_LIMITS"]["closes_memory_gate"] is False
    assert verdicts["FAIL"]["closes_memory_gate"] is False
    assert verdicts["INCONCLUSIVE"]["closes_memory_gate"] is False
    assert verdicts["BLOCKED"]["closes_memory_gate"] is False


def test_promotion_rollback_and_module_boundaries_remain_controlled() -> None:
    spec = load_yaml(SPEC_PATH)
    promotion = spec["promotion_boundary"]
    m1a = spec["m1a_boundary"]
    m1b = spec["m1b_boundary"]

    assert promotion["memory_cannot_promote_itself"] is True
    assert promotion["lifecycle"][-2:] == ["CANARY", "PROMOTED_FOR_DECLARED_SCOPE"]
    assert "affected_scenarios_replayed" in promotion["rollback_requirements"]
    assert set(m1a["must_not_choose"]) == {
        "database_vendor",
        "retrieval_algorithm",
        "embedding_model",
    }
    assert "namespace_and_acl_before_relevance" in m1b["required_capabilities"]
    assert "explainable_replayable_retrieval_plan" in m1b["required_capabilities"]
    assert set(m1b["must_not_implement"]) == {
        "autonomous_memory_formation",
        "shared_memory_coordination",
        "self_evolution_promotion",
    }


def test_spec_aligns_with_active_roadmap_and_development_ssot() -> None:
    spec = load_yaml(SPEC_PATH)
    roadmap = load_yaml(ROADMAP_PATH)
    development_ssot = load_yaml(DEVELOPMENT_SSOT_PATH)

    assert roadmap["current_state"] == "FOUNDATION_BASELINE"
    assert roadmap["stage_delivery_status"] == "NOT_READY"
    assert roadmap["next_milestone"] == "M1"
    assert roadmap["next_execution_sequence"][0] == (
        "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    )
    m1 = next(item for item in roadmap["milestones"] if item["id"] == "M1")
    assert m1["module_status"]["M1.0"] == "MERGED_CLOSED"
    assert m1["completed_evidence"]["M1.0"]["critical_false_green"] == 0
    assert spec["implementation_sequence"][0] == "M1.0_SPEC"
    assert development_ssot["assurance_profiles"]["DEV3"]["agent_may_downgrade"] is False
    assert "memory_write_share_promotion_forget" in (
        development_ssot["assurance_profiles"]["DEV3"]["default_for"]
    )
    assert development_ssot["active_autonomous_mandate"]["id"] == (
        "MANDATE-AUTONOMY-M1-M3"
    )
    assert development_ssot["assurance_profiles"]["DEV3"]["authorization_mode"] == (
        "standing_mandate_or_explicit_human_approval"
    )
    assert "active_mandate_covers_goal_profile_and_spec_when_dev3" in (
        development_ssot["agent_autonomy"]["auto_merge_conditions"]
    )
    assert "candidate_asset_direct_production_promotion" in (
        development_ssot["agent_autonomy"]["prohibited"]
    )
