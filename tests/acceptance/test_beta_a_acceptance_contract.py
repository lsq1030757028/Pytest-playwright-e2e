from pathlib import Path

import yaml

EVIDENCE_PATH = Path("docs/evidence/beta-a-acceptance.yaml")
PROGRAM_PATH = Path("docs/program-delivery-ssot.yaml")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_acceptance_candidate_is_bound_to_beta_a_authority() -> None:
    evidence = load_yaml(EVIDENCE_PATH)
    acceptance = evidence["acceptance"]
    assert acceptance["id"] == "BETA-A-OPERATING-ACCEPTANCE"
    assert acceptance["status"] == "CANDIDATE"
    assert acceptance["work_item_id"] == "BETA-A-ACCEPTANCE"
    assert acceptance["goal_issue"] == 95
    assert acceptance["parent_campaign_issue"] == 65
    assert acceptance["architecture_goal_issue"] == 66
    assert acceptance["governing_spec"] == (
        "SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0"
    )
    assert acceptance["assurance"] == {"development": "DEV3", "ux": "UX3"}


def test_acceptance_does_not_expand_beta_a_scope() -> None:
    scope = load_yaml(EVIDENCE_PATH)["scope"]
    assert scope["existing_governed_pack_only"] is True
    assert scope["adds_new_runtime_capability"] is False
    assert scope["requirement_to_test_generation"] is False
    assert scope["diagnosis_or_repair"] is False
    assert scope["governed_memory_resume"] is False
    assert scope["two_project_acceptance"] is False
    assert scope["scheduled_relay_reenable"] is False


def test_acceptance_binds_exact_implementation_and_closure_truth() -> None:
    evidence = load_yaml(EVIDENCE_PATH)
    implementation = evidence["implementation_truth"]
    assert implementation["pull_request"] == 98
    assert implementation["merge_commit"] == (
        "2c980826044d1bdafece52d0ad1918aaa04b06d8"
    )
    implementation_runs = implementation["exact_main_runs"]
    assert {binding["run_id"] for binding in implementation_runs.values()} == {
        31657082539,
        31657082561,
        31657082556,
        31657082555,
        31657082558,
    }

    closure = evidence["implementation_closure_truth"]
    assert closure["pull_request"] == 99
    assert closure["merge_commit"] == "77d54bd6b58b45c4fca3e458667bc46f22ff8991"
    closure_runs = closure["exact_main_runs"]
    assert {binding["run_id"] for binding in closure_runs.values()} == {
        31658000843,
        31658000842,
        31658000873,
        31658000911,
        31658000894,
    }
    for binding in (*implementation_runs.values(), *closure_runs.values()):
        assert binding["conclusion"] == "success"
        assert binding["workflow"]


def test_program_delivery_current_truth_is_acceptance_ready() -> None:
    program = load_yaml(PROGRAM_PATH)
    items = {item["work_item_id"]: item for item in program["work_items"]}
    assert program["program"]["state"] == "BETA_A_ACCEPTANCE"
    assert program["product_slices"]["BETA-A"]["state"] == "ACCEPTING"
    assert program["execution_pointer"]["active_slice"] == "BETA-A"
    assert program["execution_pointer"]["current_focus"] == "BETA-A-ACCEPTANCE"
    assert program["execution_pointer"]["critical_path"] == ["BETA-A-ACCEPTANCE"]
    assert items["BETA-A-IMPLEMENTATION"]["state"] == "CLOSED"
    assert items["BETA-A-IMPLEMENTATION"]["target_pr"] == 98
    assert items["BETA-A-ACCEPTANCE"]["state"] == "READY"
    assert program["relay_enablement"]["state"] == "DISABLED_GOVERNANCE_MIGRATION"


def test_independent_acceptance_proof_is_not_history_only() -> None:
    proof = load_yaml(EVIDENCE_PATH)["independent_acceptance_proof"]
    assert proof["workflow"] == "beta-a-acceptance"
    assert proof["historical_github_run_reverification"] == "required"
    assert proof["core_runtime_contracts"] == "required"
    assert proof["restart_recovery_contracts"] == "required"
    assert proof["critical_mutation_survivors_allowed"] == 0
    assert proof["ux3_personas"] == 3
    assert proof["ux3_repetitions_per_persona"] == 3
    assert proof["adversarial_recovery"] == "required"
    assert proof["real_docker_pytest_playwright"] == "required"
    assert proof["real_cancellation_cleanup"] == "required"
    assert proof["clean_wheel_install"] == "required"
    assert proof["packaged_cli_submit_execute_restart_replay"] == "required"
    assert proof["control_plane_container_smoke"] == "required"


def test_all_acceptance_safety_invariants_are_zero() -> None:
    invariants = load_yaml(EVIDENCE_PATH)["protected_invariants"]
    assert invariants
    assert all(value == 0 for value in invariants.values())


def test_candidate_exit_requires_fresh_main_acceptance_truth() -> None:
    exit_gate = load_yaml(EVIDENCE_PATH)["candidate_exit"]
    assert exit_gate["acceptance_pr_latest_head_green"] == "required"
    assert exit_gate["review_blockers"] == 0
    assert exit_gate["acceptance_merge_main_commit_bound"] == "required"
    assert exit_gate["main_beta_a_acceptance_green"] == "required"
    assert exit_gate["main_full_quality_green"] == "required"
    assert exit_gate["main_secret_scan_green"] == "required"
    assert exit_gate["main_codeql_green"] == "required"
    assert exit_gate["main_release_green"] == "required"
    assert exit_gate["then_program_delivery_may_close_beta_a"] is True
    assert exit_gate["then_goal_95_may_close_completed"] is True
    assert exit_gate["scheduled_relay_reenabled"] is False
