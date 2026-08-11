from pathlib import Path

import yaml

SPEC_YAML = Path("docs/specs/beta-a-durable-governed-pack.yaml")
SPEC_MD = Path("docs/specs/beta-a-durable-governed-pack-spec.md")
THREAT_MODEL = Path("docs/security/beta-a-durable-governed-pack-threat-model.md")
TEST_DESIGN = Path("docs/testing/beta-a-durable-governed-pack-test-design.md")
PARENT_SPEC = Path("docs/specs/test-agent-runtime-beta.yaml")
PROGRAM_DELIVERY = Path("docs/program-delivery-ssot.yaml")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_spec_identity_authority_and_assurance_are_bound() -> None:
    spec = load_yaml(SPEC_YAML)
    assert spec["spec"] == {
        "id": "SPEC-BETA-A-DURABLE-GOVERNED-PACK",
        "version": "0.1.0",
        "status": "CANDIDATE",
        "phase": "SPEC_ONLY",
        "goal_issue": 95,
        "parent_campaign_issue": 65,
        "architecture_goal_issue": 66,
        "parent_spec": "SPEC-TEST-AGENT-RUNTIME-BETA@0.1.0",
        "work_item_id": "BETA-A-SPEC",
        "product_slice": "BETA-A",
    }
    authority = spec["authority"]
    assert authority["owner_scope_extension_issues"] == [65, 66]
    assert authority["slice_goal_issue"] == 95
    assert authority["standing_mandate"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert authority["standing_mandate_covers_slice"] is False
    assert authority["standing_mandate_extended"] is False
    assert authority["runtime_implementation_requires_spec_merge"] is True
    assert authority["may_change_oracle_policy_permission"] is False
    assert spec["assurance"]["development"] == "DEV3"
    assert spec["assurance"]["ux"] == "UX3"
    assert spec["assurance"]["human_uat_replaced"] is False


def test_slice_is_existing_pack_only_and_keeps_later_slices_out() -> None:
    spec = load_yaml(SPEC_YAML)
    included = set(spec["slice_boundary"]["includes"])
    excluded = set(spec["slice_boundary"]["excludes"])
    assert {
        "cli_job_submit_status_result_events_cancel",
        "existing_governed_pack_manifest",
        "sqlite_wal_durable_job_state",
        "content_addressed_artifacts",
        "single_worker_lease_and_run_fencing",
        "existing_pytest_playwright_execution",
        "deterministic_verifier",
        "cancellation_and_process_tree_cleanup",
        "control_process_restart_reconciliation",
        "package_container_smoke",
        "replayable_evidence",
    } <= included
    assert {
        "requirement_to_test_generation",
        "test_patch_generation_or_modification",
        "diagnosis_and_test_repair",
        "automatic_reexecution_after_failure",
        "governed_memory_reuse",
        "cross_project_beta_acceptance",
        "autonomous_product_source_repair",
        "scheduled_relay_reenable",
    } <= excluded
    assert spec["business_outcome"]["runtime_implemented_by_this_spec_pr"] is False
    assert spec["business_outcome"]["scheduled_relay_reenabled_by_this_spec"] is False


def test_entrypoint_and_submission_are_bounded_and_idempotent() -> None:
    spec = load_yaml(SPEC_YAML)
    entrypoint = spec["entrypoint"]
    assert entrypoint["user_commands"] == {
        "submit": "test-agent job submit",
        "status": "test-agent job status",
        "result": "test-agent job result",
        "events": "test-agent job events",
        "cancel": "test-agent job cancel",
    }
    assert entrypoint["operator_bootstrap"]["reference_command"] == "test-agent runtime serve"
    assert entrypoint["operator_bootstrap"]["user_product_entrypoint"] is False
    assert entrypoint["state_locator"]["type"] == "EXPLICIT_STATE_DIR"
    assert entrypoint["state_locator"]["same_state_dir_required_for_runtime_and_cli"] is True
    assert entrypoint["output"]["stable_json_mode_required"] is True
    assert entrypoint["output"]["raw_unbounded_logs_in_default_output"] is False

    submission = spec["submission"]
    assert submission["fingerprint_binds_all_required_fields"] is True
    assert submission["same_key_same_fingerprint"] == "IDEMPOTENT_SAME_JOB"
    assert submission["same_key_changed_fingerprint"] == "EXPLICIT_CONFLICT"
    assert {
        "floating_project_ref",
        "missing_oracle_authority",
        "unknown_or_mutable_pack_manifest",
        "unbounded_budget",
        "product_source_write_permission",
        "freeform_shell_or_pytest_argument_string",
    } <= set(submission["rejects"])


def test_governed_pack_prevents_partial_pack_false_green() -> None:
    pack = load_yaml(SPEC_YAML)["governed_pack_manifest"]
    assert {
        "pack_id",
        "pack_version",
        "commit_sha",
        "selected_node_ids",
        "required_node_ids",
        "node_oracle_bindings",
    } <= set(pack["required_fields"])
    assert pack["immutable_and_hash_bound"] is True
    assert pack["selected_node_ids_unique"] is True
    assert pack["required_node_ids_subset_of_selected"] is True
    assert pack["exact_node_ids_required"] is True
    assert pack["freeform_pytest_args_allowed"] is False
    assert pack["user_supplied_shell_fragments_allowed"] is False
    assert pack["collection_preflight_required"] is True
    assert pack["collection_manifest_hash_required"] is True
    assert pack["required_nodes_must_collect"] is True
    assert pack["required_nodes_must_execute_for_verified_success"] is True
    assert pack["skipped_required_node_allows_success"] is False
    assert pack["xfailed_required_node_allows_success"] is False
    assert pack["deselected_required_node_allows_success"] is False


def test_reference_runtime_preserves_parent_security_boundaries() -> None:
    spec = load_yaml(SPEC_YAML)
    profile = spec["runtime_reference_profile"]
    assert profile["control_plane_instances"] == 1
    assert profile["workers_per_job"] == 1
    assert profile["browser_contexts_per_attempt"] == 1
    assert profile["job_store"]["backend"] == "SQLITE_WAL"
    assert profile["job_store"]["synchronous"] == "FULL"
    assert profile["artifact_store"]["backend"] == "CONTENT_ADDRESSED_FILESYSTEM"
    assert profile["artifact_store"]["hash"] == "SHA256"
    assert profile["artifact_store"]["temp_write_hash_fsync_atomic_finalize"] == "required"

    sandbox = profile["sandbox"]
    assert sandbox["isolated_worker_required"] is True
    assert sandbox["product_tree_read_only"] is True
    assert sandbox["host_secret_environment_inheritance"] == "forbidden"
    assert sandbox["host_socket_mounts"] == "forbidden"
    assert sandbox["path_traversal"] == "reject"
    assert sandbox["symlink_escape"] == "reject"
    assert sandbox["network_default"] == "deny"

    process = profile["process_execution"]
    assert process["shell_interpolation"] == "forbidden"
    assert process["argv_list_only"] is True
    assert process["command_family"] == "PYTHON_MODULE_PYTEST"
    assert process["adapter_generated_command_only"] is True


def test_job_lifecycle_and_attempt_fencing_are_deterministic() -> None:
    spec = load_yaml(SPEC_YAML)
    lifecycle = spec["job_lifecycle"]
    states = lifecycle["allowed_states"]
    terminal = lifecycle["terminal_states"]
    assert len(states) == len(set(states))
    assert set(terminal) <= set(states)
    assert lifecycle["append_only_events"] is True
    assert lifecycle["monotonic_event_sequence"] is True
    assert lifecycle["expected_revision_required_for_transition"] is True
    assert lifecycle["stale_revision_result"] == "EXPLICIT_CONFLICT"
    assert lifecycle["terminal_state_immutable"] is True
    assert lifecycle["terminal_mapping"] == {
        "VERIFIED_SUCCESS": "SUCCEEDED",
        "PRODUCT_DEFECT": "FAILED",
        "TEST_DEFECT": "FAILED",
        "ENVIRONMENT_FAILURE": "FAILED",
        "INSUFFICIENT_EVIDENCE": "BLOCKED",
        "ORACLE_CONFLICT": "BLOCKED",
        "POLICY_BLOCKED": "BLOCKED",
        "CANCELLED": "CANCELLED",
        "TIMED_OUT": "TIMED_OUT",
    }

    attempt = spec["attempt_lifecycle"]
    assert attempt["lease_token_required_for_mutation_after_claim"] is True
    assert attempt["lease_heartbeat_required"] is True
    assert attempt["heartbeat_interval_seconds"] == 2
    assert attempt["lease_ttl_seconds"] == 10
    assert attempt["tests_use_injectable_clock_not_wall_sleep"] is True
    assert attempt["command_started_marker_durable_before_spawn"] is True
    assert attempt["maximum_command_launches_per_job"] == 1
    assert attempt["automatic_execution_retries"] == 0


def test_restart_reconciliation_is_safe_without_claiming_beta_d() -> None:
    restart = load_yaml(SPEC_YAML)["restart_reconciliation"]
    assert restart["safe_recovery_cases"] == {
        "accepted_without_attempt": "MAY_CONTINUE",
        "leased_before_command_started": "MAY_RECLAIM_AFTER_LEASE_EXPIRY",
        "command_started_without_terminal_attempt": "BLOCK_NO_REEXECUTION",
        "durable_evidence_without_final_verdict": "REVERIFY_DETERMINISTICALLY",
        "terminal_job": "RETURN_EXISTING_RESULT",
    }
    assert restart["uncertain_side_effect_auto_reexecute"] == "forbidden"
    assert restart["duplicate_execution_after_restart_count"] == 0
    assert restart["beta_a_claims_full_resume_after_active_execution"] is False
    assert restart["full_active_execution_resume_deferred_to_slice"] == "BETA-D"


def test_verifier_requires_complete_evidence_not_exit_code() -> None:
    verifier = load_yaml(SPEC_YAML)["verifier"]
    assert verifier["authority"] == "DETERMINISTIC_VERIFIER"
    assert verifier["model_output_authority"] == "CANDIDATE_ONLY"
    assert {
        "terminal_attempt_completed",
        "command_exit_success",
        "all_required_nodes_collected",
        "all_required_nodes_executed",
        "all_required_nodes_passed",
        "required_evidence_complete",
        "all_artifact_hashes_valid",
        "project_pack_environment_bindings_match",
        "no_product_source_diff",
        "no_policy_or_oracle_conflict",
        "cleanup_verified",
    } <= set(verifier["verified_success_requires"])
    assert verifier["exit_code_alone_may_produce_verified_success"] is False
    assert verifier["assertion_failure_with_valid_governed_oracle_binding"] == "PRODUCT_DEFECT"
    assert verifier["collection_import_fixture_or_test_structure_failure"] == "TEST_DEFECT"
    assert verifier["browser_dependency_runtime_or_sandbox_failure"] == "ENVIRONMENT_FAILURE"
    assert verifier["missing_stale_tampered_or_conflicting_evidence"] == "INSUFFICIENT_EVIDENCE"


def test_cancellation_requires_process_tree_and_cleanup_truth() -> None:
    cancellation = load_yaml(SPEC_YAML)["cancellation"]
    assert cancellation["cancel_request_durable"] is True
    assert cancellation["cancel_request_idempotent"] is True
    assert cancellation["worker_must_observe_cancel_before_new_step"] is True
    assert cancellation["active_process_tree_termination_required"] is True
    assert cancellation["graceful_termination_seconds"] == 10
    assert cancellation["force_kill_after_grace"] is True
    assert cancellation["lease_revoke_required"] is True
    assert cancellation["partial_evidence_preserved"] is True
    assert cancellation["cleanup_verification_required_before_cancelled_terminal"] is True
    assert cancellation["surviving_process_or_unverified_cleanup_may_return_cancelled"] is False
    assert cancellation["cancel_after_terminal_returns_existing_terminal_truth"] is True


def test_budgets_are_bounded_and_no_retry_loop_exists() -> None:
    budgets = load_yaml(SPEC_YAML)["budgets"]
    assert budgets == {
        "wall_clock_job_minutes_max": 45,
        "execution_attempt_minutes_max": 15,
        "execution_attempts_max": 1,
        "concurrent_workers_per_job": 1,
        "browser_contexts_per_attempt": 1,
        "artifact_mebibytes_per_job_max": 500,
        "freeform_retry_count": 0,
        "budget_exhaustion_widens_limit": False,
    }


def test_critical_mutation_catalog_and_zero_invariants_are_complete() -> None:
    spec = load_yaml(SPEC_YAML)
    assert set(spec["critical_mutation_catalog"]) == {
        "REMOVE_SUBMISSION_FINGERPRINT_REBOUND_REJECTION",
        "REMOVE_EXPECTED_REVISION_OR_LEASE_FENCING",
        "REMOVE_REQUIRED_NODE_COLLECTION_COMPLETENESS",
        "ALLOW_SKIPPED_OR_DESELECTED_REQUIRED_NODE_SUCCESS",
        "REMOVE_EVIDENCE_COMPLETENESS_BEFORE_SUCCESS",
        "REMOVE_ARTIFACT_HASH_VERIFICATION",
        "REMOVE_PRODUCT_SOURCE_DIFF_REJECTION",
        "REMOVE_CANCELLATION_PROCESS_TREE_PROOF",
        "AUTO_REEXECUTE_UNCERTAIN_RESTART",
        "ALLOW_EXIT_CODE_ONLY_SUCCESS",
    }
    assert spec["critical_mutation_survivors_allowed"] == 0
    zero_keys = {
        "critical_false_green_count",
        "unauthorized_product_source_write_count",
        "unauthorized_oracle_policy_permission_change_count",
        "unverifiable_success_verdict_count",
        "duplicate_execution_after_restart_count",
        "idempotency_key_rebound_accepted_count",
        "stale_worker_state_write_count",
        "required_node_not_executed_but_success_count",
        "artifact_hash_mismatch_but_success_count",
        "child_process_survivor_after_cancelled_count",
        "secret_or_personal_data_exposure_count",
        "unbounded_retry_or_spend_count",
    }
    invariants = spec["protected_invariants"]
    assert zero_keys <= set(invariants)
    assert all(invariants[key] == 0 for key in zero_keys)


def test_parent_architecture_is_narrowed_not_weakened() -> None:
    spec = load_yaml(SPEC_YAML)
    parent = load_yaml(PARENT_SPEC)
    assert parent["product"]["operational_entrypoint"] == "CLI"
    assert parent["durable_runtime"]["beta_job_store"]["backend"] == "SQLITE_WAL"
    assert parent["durable_runtime"]["artifact_store"]["hash"] == "SHA256"
    assert parent["success_authority"] == "DETERMINISTIC_VERIFIER"
    assert parent["workspace"]["product_source_write_allowed"] is False
    assert parent["workspace"]["network_default"] == "DENY"
    assert spec["supported_profile"]["deployment"] == "SINGLE_NODE_DURABLE"
    assert spec["supported_profile"]["product_source_agent_write"] is False
    assert spec["supported_profile"]["network_default"] == "DENY"


def test_program_delivery_truth_and_post_spec_transition_are_consistent() -> None:
    program = load_yaml(PROGRAM_DELIVERY)
    items = {item["work_item_id"]: item for item in program["work_items"]}
    assert program["program"]["state"] == "PRE_BETA_A"
    assert program["execution_pointer"]["active_slice"] == "BETA-A"
    assert program["execution_pointer"]["current_focus"] == "BETA-A-SPEC"
    assert program["execution_pointer"]["critical_path"][0] == "BETA-A-SPEC"
    assert items["BETA-A-SPEC"]["state"] == "READY"
    assert items["BETA-A-IMPLEMENTATION"]["state"] == "BLOCKED"

    transition = load_yaml(SPEC_YAML)["post_spec_transition"]
    assert transition["program_delivery_work_item_to_close"] == "BETA-A-SPEC"
    assert transition["program_delivery_work_item_to_ready"] == "BETA-A-IMPLEMENTATION"
    assert set(transition["runtime_implementation_may_start_only_after"]) == {
        "spec_merged_to_main",
        "post_merge_spec_gate_green",
        "post_merge_full_quality_green",
        "post_merge_security_green",
    }
    assert transition["scheduled_relay_reenabled"] is False


def test_human_assets_define_uncertainty_false_green_and_ux_contracts() -> None:
    spec_md = SPEC_MD.read_text(encoding="utf-8")
    threat = THREAT_MODEL.read_text(encoding="utf-8")
    design = TEST_DESIGN.read_text(encoding="utf-8")

    assert "SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0" in spec_md
    assert "ABANDONED_UNCERTAIN" in spec_md
    assert "Exit code alone can never produce `VERIFIED_SUCCESS`" in spec_md
    assert "must not falsely report `CANCELLED`" in spec_md
    assert "Full active resume stays BETA-D" not in spec_md
    assert "Full resume of an active execution is BETA-D scope" in spec_md

    assert "Green process with incomplete governed pack" in threat
    assert "Crash after launch, before result" in threat
    assert "Cancellation with surviving process" in threat
    assert "Scheduled Relay" in threat

    assert "Governed-pack false-green matrix" in design
    assert "Restart matrix" in design
    assert "Cancellation matrix" in design
    assert "Critical mutation survivors: `0`" in design
    assert "UX3 journey design" in design
