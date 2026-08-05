from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "docs/specs/ux1-todomvc-mutation-proof.yaml"
CATALOG_PATH = ROOT / "tests/assets/ux/ux1/mutation-catalog.yaml"
NEGATIVE_PATH = ROOT / "tests/assets/ux/ux1/negative-cases.yaml"
PREIMAGE_PATH = ROOT / "tests/assets/ux/ux1/target-index-preimage.html"
UX0_CATALOG_PATH = ROOT / "benchmarks/ux/ux0/catalog.yaml"
UX_STATUS_PATH = ROOT / "docs/ux-assurance-status.md"
PROJECT_STATUS_PATH = ROOT / "docs/implementation-status.md"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    return sha256_bytes(content.encode("utf-8"))


def without_prefix(value: str) -> str:
    return value.removeprefix("sha256:")


def test_spec_identity_parent_runtime_and_protected_boundaries() -> None:
    spec = load_yaml(SPEC_PATH)

    assert spec["spec_id"] == "SPEC-UX1-TODOMVC-MUTATION-PROOF"
    assert spec["version"] == "1.0.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 34
    assert spec["mandate_ref"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert spec["parent_spec_ref"] == "SPEC-UX0-SYNTHETIC-USER@1.0.0"
    assert spec["parent_runtime_ref"] == "UX0-SYNTHETIC-USER-SHADOW@1.0.0"
    assert spec["parent_runtime_merge"] == (
        "f687fd9c30873c4a81d9ffb57b20459fdcebe4ee"
    )
    assert spec["parent_runtime_closure"] == (
        "8760cf785ecb4d75415b8a155739fc7d69e7546d"
    )
    assert spec["assurance"] == {
        "spec_phase": "DEV3",
        "implementation_phase": "DEV3",
        "ux_level": "UX3",
        "threat_model_required": True,
        "autonomous_execution_allowed_under_active_mandate": True,
        "runtime_mode": "SHADOW",
        "release_effect": "NONBLOCKING_SHADOW",
        "human_uat": "REQUIRED",
        "advisory_gate": "DISABLED",
        "blocking_gate": "DISABLED",
    }
    assert {
        "runtime_mode_remains_shadow",
        "release_effect_remains_nonblocking_shadow",
        "human_uat_remains_required",
        "ai_candidate_finding_is_not_kill_evidence",
        "experience_oracle_is_not_actor_visible",
        "mutation_metadata_is_not_actor_visible",
        "repository_and_production_sources_are_not_mutated",
        "exact_restoration_required_before_pass",
        "dirty_target_cannot_pass",
        "m1a_remains_current_main_module",
        "m1_memory_gate_remains_open",
        "stage_delivery_remains_not_ready",
    } == set(spec["protected_invariants"])


def test_pinned_target_preimage_matches_canonical_snapshot() -> None:
    spec = load_yaml(SPEC_PATH)
    catalog = load_yaml(CATALOG_PATH)
    source = PREIMAGE_PATH.read_bytes()
    digest = sha256_bytes(source)
    mutable = spec["source_truth"]["mutable_files"][0]
    catalog_mutable = catalog["target"]["mutable_file"]

    assert len(source) == 1459
    assert digest == "8abcb565e24e7fdbe75feb21f986e9b7550173c04122727e4e07e7ec9c4d5f70"
    assert spec["source_truth"]["target_revision"] == (
        "4a2344b2207a72c680e5c559c72617498fb5b75b"
    )
    assert mutable["path"] == "index.html"
    assert mutable["git_blob_sha1"] == "2f5a055475c5a4810bbf948f6b5acf6ed45fdc4a"
    assert without_prefix(mutable["preimage_sha256"]) == digest
    assert mutable["byte_length"] == len(source)
    assert catalog["target"]["revision"] == spec["source_truth"]["target_revision"]
    assert catalog_mutable == mutable


def test_five_ordered_mutations_cover_all_required_families() -> None:
    spec = load_yaml(SPEC_PATH)
    catalog = load_yaml(CATALOG_PATH)
    mutations = catalog["mutations"]

    expected_ids = [f"UXM-{index:03d}" for index in range(1, 6)]
    expected_families = [
        "MISSING_FEEDBACK",
        "VISIBLE_SUCCESS_STATE_LOSS",
        "KEYBOARD_FOCUS_SEMANTIC_BARRIER",
        "INTERRUPTED_RESUME_FAILURE",
        "FILTER_ROUTE_STATE_DRIFT",
    ]
    assert [item["mutation_id"] for item in mutations] == expected_ids
    assert [item["family"] for item in mutations] == expected_families
    assert spec["mutation_families"] == expected_families
    assert spec["acceptance_gates"]["required_mutation_families"] == 5
    assert spec["acceptance_gates"]["required_mutation_ids"] == expected_ids
    assert all(item["severity"] == "CRITICAL" for item in mutations)
    assert all(item["expected_replacement_count"] == 1 for item in mutations)
    assert all(item["minimum_evidence_level"] == "E3" for item in mutations)
    assert all(item["disallowed_kill_basis"] == "AI_CANDIDATE_ONLY" for item in mutations)


def test_every_mutation_matches_once_has_expected_postimage_and_restores_exactly() -> None:
    catalog = load_yaml(CATALOG_PATH)
    original = PREIMAGE_PATH.read_text(encoding="utf-8")
    original_digest = sha256_text(original)

    for mutation in catalog["mutations"]:
        search = mutation["search_text"]
        replacement = mutation["replacement_text"]
        assert mutation["target_path"] == "index.html"
        assert without_prefix(mutation["preimage_sha256"]) == original_digest
        assert sha256_text(search) == without_prefix(mutation["search_sha256"])
        assert sha256_text(replacement) == without_prefix(
            mutation["replacement_sha256"]
        )
        assert original.count(search) == mutation["expected_replacement_count"] == 1

        mutated = original.replace(search, replacement)
        assert sha256_text(mutated) == without_prefix(mutation["postimage_sha256"])
        assert mutated != original

        restored = original.encode("utf-8")
        assert sha256_bytes(restored) == original_digest
        assert restored == PREIMAGE_PATH.read_bytes()


def test_mutations_map_to_existing_journeys_oracles_and_checkpoints() -> None:
    mutation_catalog = load_yaml(CATALOG_PATH)
    ux0_catalog = load_yaml(UX0_CATALOG_PATH)
    journeys = {
        f"{journey['journey_id']}@{journey['revision']}": journey
        for journey in ux0_catalog["journeys"]
    }
    oracle_refs = {
        f"{journey['oracle']['oracle_id']}@{journey['oracle']['revision']}": journey[
            "oracle"
        ]
        for journey in ux0_catalog["journeys"]
    }

    mapped_journeys: set[str] = set()
    mapped_oracles: set[str] = set()
    for mutation in mutation_catalog["mutations"]:
        assert mutation["affected_journey_refs"]
        assert mutation["oracle_refs"]
        assert mutation["expected_failed_checkpoints"]
        mapped_journeys.update(mutation["affected_journey_refs"])
        mapped_oracles.update(mutation["oracle_refs"])

        available_checkpoints: set[str] = set()
        for journey_ref in mutation["affected_journey_refs"]:
            assert journey_ref in journeys
            available_checkpoints.update(
                journeys[journey_ref]["oracle"]["required_checkpoints"]
            )
        for oracle_ref in mutation["oracle_refs"]:
            assert oracle_ref in oracle_refs
        assert set(mutation["expected_failed_checkpoints"]) <= available_checkpoints

    assert mapped_journeys == {
        "novice-add-task@1.0.0",
        "returning-filter-persistence@1.0.0",
        "keyboard-primary@1.0.0",
        "interrupted-resume@1.0.0",
    }
    assert mapped_oracles == {
        "UX-ORACLE-ADD-TASK@1.0.0",
        "UX-ORACLE-FILTER-PERSIST@1.0.0",
        "UX-ORACLE-KEYBOARD@1.0.0",
        "UX-ORACLE-INTERRUPTED@1.0.0",
    }


def test_mutation_contract_is_exact_bounded_and_command_free() -> None:
    spec = load_yaml(SPEC_PATH)
    catalog = load_yaml(CATALOG_PATH)
    contract = spec["mutation_contract"]
    catalog_contract = catalog["mutation_contract"]
    serialized = yaml.safe_dump(catalog, allow_unicode=True).lower()

    assert contract["application_type"] == "EXACT_TEXT_REPLACE"
    assert set(contract["allowed_operations"]) == {
        "READ_FILE",
        "EXACT_TEXT_REPLACE",
        "HASH_FILE",
        "RESTORE_BYTES",
    }
    assert {
        "REGEX_REPLACE",
        "ARBITRARY_COMMAND",
        "SHELL_PAYLOAD",
        "PATH_TRAVERSAL",
        "NETWORK_WRITE",
        "REPOSITORY_SOURCE_WRITE",
        "PRODUCTION_WRITE",
    } == set(contract["forbidden_operations"])
    assert contract["path_requirements"] == {
        "relative_only": True,
        "remain_inside_target_checkout": True,
        "symlink_escape_forbidden": True,
    }
    assert contract["isolation"]["one_mutation_per_checkout"] is True
    assert contract["isolation"]["synthetic_fixture_only"] is True
    assert contract["isolation"]["cleanup_on_every_outcome"] is True
    assert catalog_contract["regex_allowed"] is False
    assert catalog_contract["arbitrary_command_allowed"] is False
    assert catalog_contract["path_traversal_forbidden"] is True
    assert "command:" not in serialized
    assert "../../" not in serialized


def test_hidden_mutation_metadata_never_enters_actor_input() -> None:
    boundary = load_yaml(SPEC_PATH)["hidden_evaluation_boundary"]

    assert set(boundary["actor_visible"]) == {
        "user_goal",
        "synthetic_user_profile",
        "experience_environment",
        "visible_application_state",
        "allowed_capabilities",
        "budgets",
    }
    forbidden = set(boundary["actor_input_forbidden_fields"])
    assert {
        "mutation_id",
        "mutation_family",
        "mutation_patch",
        "changed_file",
        "expected_failed_checkpoint",
        "preferred_locator_sequence",
        "expected_phase_verdict",
        "evaluator_scoring_key",
    } == forbidden
    assert forbidden.isdisjoint(boundary["actor_visible"])
    assert boundary["leakage_action"] == "INVALID_EVIDENCE"


def test_state_machine_is_closed_and_requires_restore_before_pass() -> None:
    machine = load_yaml(SPEC_PATH)["state_machine"]
    success_path = machine["success_path"]
    transitions = machine["transitions"]
    all_states = set(transitions)

    assert success_path[0] == "PLANNED"
    assert success_path[-1] == "CLOSED_PASS"
    assert "RESTORING" in success_path
    assert "RESTORE_VERIFIED" in success_path
    assert "RESTORED_RUNNING" in success_path
    for source, target in zip(success_path, success_path[1:], strict=True):
        assert target in transitions[source]
    for targets in transitions.values():
        assert set(targets) <= all_states
    for failure_state in machine["failure_states"]:
        assert transitions[failure_state] == []
    assert "MUTATION_APPLYING" not in transitions["PLANNED"]
    assert "CLOSED_PASS" not in transitions["MUTATION_KILLED"]
    assert transitions["CLOSED_PASS"] == []
    assert machine["later_phase_after_required_failure_forbidden"] is True
    assert machine["every_transition_requires_event"] is True


def test_negative_assets_cover_catalog_application_adjudication_restore_and_replay() -> None:
    cases = load_yaml(NEGATIVE_PATH)

    assert len(cases["invalid_catalog_cases"]) >= 10
    catalog_errors = {
        item["expected_error"] for item in cases["invalid_catalog_cases"]
    }
    assert {
        "TARGET_PATH_DENIED",
        "MUTATION_OPERATION_DENIED",
        "INVALID_MUTATION_CONTRACT",
        "DUPLICATE_MUTATION_ID",
        "NONCONTIGUOUS_MUTATION_ID",
        "ORACLE_MAPPING_REQUIRED",
        "KILL_EVIDENCE_INSUFFICIENT",
        "TARGET_SCOPE_DENIED",
    } <= catalog_errors
    assert {item["expected_result"] for item in cases["application_cases"]} == {
        "INVALID"
    }
    assert {item["expected_result"] for item in cases["restoration_cases"]} == {
        "INVALID",
        "RESTORE_VERIFIED",
    }
    assert any(
        item["expected_result"] == "SURVIVED"
        and item["expected_error"] == "AI_ONLY_FINDING_NOT_KILL"
        for item in cases["phase_adjudication_cases"]
    )
    assert any(
        item["expected_result"] == "INVALID"
        and item.get("expected_error") == "ARTIFACT_TAMPERED"
        for item in cases["replay_cases"]
    )
    assert ["MUTATION_KILLED", "CLOSED_PASS"] in cases["transition_cases"][
        "denied"
    ]


def test_verdict_and_acceptance_gates_fail_closed_without_advisory_promotion() -> None:
    spec = load_yaml(SPEC_PATH)
    verdict = spec["verdict_contract"]
    gates = spec["acceptance_gates"]

    assert "ai_candidate_not_used_as_authority" in verdict["per_mutation"]["KILLED"][
        "requirements"
    ]
    assert "only_ai_candidate_finding_observed" in verdict["per_mutation"][
        "SURVIVED"
    ]["conditions"]
    assert "dirty_or_inexact_restoration" in verdict["per_mutation"]["INVALID"][
        "conditions"
    ]
    assert "any_required_mutation_survived" in verdict["campaign"]["FAIL"][
        "conditions"
    ]
    assert gates["baseline_false_positive_count"] == 0
    assert gates["critical_mutation_kill_rate_percent"] == 100
    assert gates["critical_false_green_count"] == 0
    assert gates["exact_restore_percent"] == 100
    assert gates["replay_percent"] == 100
    assert gates["hidden_metadata_leakage_count"] == 0
    assert gates["ai_only_kills"] == 0
    assert gates["undeclared_changed_files"] == 0
    assert gates["advisory_gate_enabled"] is False
    assert gates["blocking_gate_enabled"] is False
    assert gates["human_uat_required"] is True


def test_runner_is_not_implemented_and_project_truth_remains_open() -> None:
    spec = load_yaml(SPEC_PATH)
    ux_status = UX_STATUS_PATH.read_text(encoding="utf-8")
    project_status = PROJECT_STATUS_PATH.read_text(encoding="utf-8")

    assert spec["runner_port_boundary"]["implementation_status"] == "NOT_IMPLEMENTED"
    assert "TodoMVC UX Mutation Proof：SPEC_DRAFT" in ux_status
    assert "UX Mutation Proof Runner：NOT_IMPLEMENTED" in ux_status
    assert "Gate Mode：`SHADOW_NONBLOCKING`" in ux_status
    assert "Blocking Release Gate：DISABLED" in ux_status
    assert "Human UAT：`REQUIRED`" in ux_status

    assert "TodoMVC UX Mutation Proof：SPEC_DRAFT" in project_status
    assert "M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT" in project_status
    assert "M1 Memory Gate：0 / 1" in project_status
    assert "Stage Delivery：NOT_READY" in project_status
