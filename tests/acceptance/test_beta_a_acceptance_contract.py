from pathlib import Path

import yaml

EVIDENCE_PATH = Path("docs/evidence/beta-a-acceptance.yaml")
PROGRAM_PATH = Path("docs/program-delivery-ssot.yaml")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_acceptance_is_verified_and_bound_to_beta_a_authority() -> None:
    evidence = load_yaml(EVIDENCE_PATH)
    acceptance = evidence["acceptance"]
    assert acceptance["id"] == "BETA-A-OPERATING-ACCEPTANCE"
    assert acceptance["status"] == "VERIFIED"
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


def test_acceptance_binds_all_three_exact_main_truth_layers() -> None:
    evidence = load_yaml(EVIDENCE_PATH)
    implementation = evidence["implementation_truth"]
    assert implementation["pull_request"] == 98
    assert implementation["merge_commit"] == (
        "2c980826044d1bdafece52d0ad1918aaa04b06d8"
    )
    assert {binding["run_id"] for binding in implementation["exact_main_runs"].values()} == {
        31657082539,
        31657082561,
        31657082556,
        31657082555,
        31657082558,
    }

    closure = evidence["implementation_closure_truth"]
    assert closure["pull_request"] == 99
    assert closure["merge_commit"] == "77d54bd6b58b45c4fca3e458667bc46f22ff8991"
    assert {binding["run_id"] for binding in closure["exact_main_runs"].values()} == {
        31658000843,
        31658000842,
        31658000873,
        31658000911,
        31658000894,
    }

    verified = evidence["verified_main_truth"]
    assert verified["pull_request"] == 100
    assert verified["merge_commit"] == "056d8819e6b7da507c8f9ed1be3ab8fca77f046a"
    assert {binding["run_id"] for binding in verified["exact_main_runs"].values()} == {
        31658662384,
        31658662425,
        31658662439,
        31658662475,
        31658662468,
    }

    for section in (implementation, closure, verified):
        for binding in section["exact_main_runs"].values():
            assert binding["conclusion"] == "success"
            assert binding["workflow"]


def test_program_delivery_handoff_closes_beta_a_and_readies_beta_b_spec() -> None:
    program = load_yaml(PROGRAM_PATH)
    items = {item["work_item_id"]: item for item in program["work_items"]}
    assert program["program"]["state"] == "PRE_BETA_B"
    assert program["product_slices"]["BETA-A"]["state"] == "CLOSED"
    assert program["product_slices"]["BETA-B"]["state"] == "PREPARING"
    assert program["execution_pointer"]["active_slice"] == "BETA-B"
    assert program["execution_pointer"]["current_focus"] == "BETA-B-SPEC"
    assert program["execution_pointer"]["critical_path"] == [
        "BETA-B-SPEC",
        "BETA-B-IMPLEMENTATION",
        "BETA-B-ACCEPTANCE",
    ]
    assert items["BETA-A-ACCEPTANCE"]["state"] == "CLOSED"
    assert items["BETA-A-ACCEPTANCE"]["target_pr"] == 100
    assert items["BETA-B-SPEC"]["state"] == "READY"
    assert items["BETA-B-SPEC"]["authority_issue"] == 101
    assert items["BETA-B-IMPLEMENTATION"]["state"] == "BLOCKED"
    assert items["BETA-B-ACCEPTANCE"]["state"] == "BLOCKED"
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


def test_verified_result_allows_program_closure_but_not_relay() -> None:
    result = load_yaml(EVIDENCE_PATH)["verification_result"]
    assert result["candidate_exit_satisfied"] is True
    assert result["acceptance_main_verified"] is True
    assert result["beta_a_may_close"] is True
    assert result["goal_95_may_close_after_program_delivery_closure_main_verification"] is True
    assert result["relay_reenable_authorized"] is False
