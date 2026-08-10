from collections import defaultdict, deque
from pathlib import Path

import yaml

SPEC_YAML = Path("docs/specs/program-delivery-ssot.yaml")
SPEC_MD = Path("docs/specs/program-delivery-ssot-spec.md")
THREAT_MODEL = Path("docs/security/program-delivery-ssot-threat-model.md")
TEST_DESIGN = Path("docs/testing/program-delivery-ssot-test-design.md")


def load_spec() -> dict[str, object]:
    return yaml.safe_load(SPEC_YAML.read_text(encoding="utf-8"))


def test_spec_is_goal_bound_and_spec_only() -> None:
    spec = load_spec()
    meta = spec["spec"]
    assert meta["id"] == "SPEC-PROGRAM-DELIVERY-SSOT"
    assert meta["version"] == "1.0.0"
    assert meta["status"] == "CANDIDATE"
    assert meta["goal_issue"] == 91
    assert meta["parent_campaign_issue"] == 65
    assert meta["architecture_goal_issue"] == 66
    assert meta["relay_goal_issue"] == 49
    assert meta["parallel_control_goal_issue"] == 55
    assert meta["assurance"] == {"development": "DEV3", "ux": "UX0"}
    assert meta["phase"] == "SPEC_ONLY"
    assert spec["business_outcome"]["scheduled_relay_reenabled_by_this_spec"] is False


def test_responsibility_planes_are_separated() -> None:
    spec = load_spec()
    planes = spec["responsibility_planes"]
    assert planes["authorization"]["answers"] == "MAY_DO"
    assert planes["authorization"]["delivery_ssot_may_expand_authority"] is False
    assert planes["delivery"]["answers"] == "SHOULD_DO_NEXT"
    assert planes["delivery"]["future_authoritative_source"] == "docs/program-delivery-ssot.yaml"
    assert planes["execution_ownership"]["answers"] == "WHO_DOES_IT"
    assert planes["execution_ownership"]["may_define_product_priority"] is False
    assert planes["execution_ownership"]["may_define_product_completion_truth"] is False


def test_beta_slice_dependencies_exist_and_are_acyclic() -> None:
    spec = load_spec()
    slices = spec["product"]["slices"]
    assert set(slices) == {"BETA-A", "BETA-B", "BETA-C", "BETA-D", "BETA-E"}
    assert slices["BETA-A"]["dependencies"] == []
    assert slices["BETA-B"]["dependencies"] == ["BETA-A"]
    assert slices["BETA-C"]["dependencies"] == ["BETA-B"]
    assert slices["BETA-D"]["dependencies"] == ["BETA-A", "BETA-C"]
    assert slices["BETA-E"]["dependencies"] == ["BETA-B", "BETA-C", "BETA-D"]

    incoming = {slice_id: 0 for slice_id in slices}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for slice_id, item in slices.items():
        for dependency in item["dependencies"]:
            assert dependency in slices
            outgoing[dependency].append(slice_id)
            incoming[slice_id] += 1

    queue = deque(sorted(key for key, value in incoming.items() if value == 0))
    visited: list[str] = []
    while queue:
        slice_id = queue.popleft()
        visited.append(slice_id)
        for child in outgoing[slice_id]:
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    assert len(visited) == len(slices)


def test_capability_lanes_map_to_product_slices_not_sequence() -> None:
    spec = load_spec()
    lanes = spec["capability_lanes"]
    assert lanes["M1_MEMORY"]["primary_slices"] == ["BETA-D"]
    assert lanes["M5_DURABLE_RUNTIME"]["primary_slices"] == ["BETA-A", "BETA-D"]
    assert lanes["UX_FP_FN_ASSURANCE"]["primary_slices"] == ["BETA-C", "BETA-E"]
    assert lanes["M4_BOUNDED_ORCHESTRATION"]["only_when_slice_requires"] is True
    assert spec["critical_path_contract"]["milestone_number_may_imply_priority"] is False


def test_critical_path_requires_product_mapping() -> None:
    spec = load_spec()
    required = set(spec["critical_path_contract"]["work_item_requires_any_mapping"])
    assert required == {"blocks_slice", "closes_slice", "unblocks_integration"}
    assert spec["critical_path_contract"]["unmapped_horizontal_default_class"] == "PARALLEL_SUPPORT"


def test_selection_policy_is_product_first_and_deterministic() -> None:
    spec = load_spec()
    policy = spec["selection_policy"]
    assert policy["classes_in_order"] == [
        "SECURITY_CORRECTNESS_REPAIR",
        "ACTIVE_SLICE_BLOCKER",
        "ACTIVE_SLICE_CLOSER",
        "DEPENDENCY_UNBLOCKING_INTEGRATION",
        "ACTIVE_OR_NEXT_SLICE_PARALLEL_CAPABILITY",
        "NEXT_SLICE_REQUIRED_PREPARATION",
        "UNMAPPED_HORIZONTAL_INFRASTRUCTURE",
    ]
    assert policy["tie_break"] == ["explicit_priority_desc", "work_item_id_asc"]
    assert "milestone_number" in policy["forbidden_priority_signals"]
    assert "claim_registry_sequence" in policy["forbidden_priority_signals"]


def test_only_one_planned_machine_delivery_authority_exists() -> None:
    spec = load_spec()
    roles = spec["planned_source_roles"]
    authoritative = [path for path, role in roles.items() if role == "AUTHORITATIVE_DELIVERY"]
    assert authoritative == ["docs/program-delivery-ssot.yaml"]
    assert roles["docs/implementation-status.md"] == "GENERATED_VIEW"
    assert roles["docs/agent-os-roadmap.yaml"] == "REFERENCE_ARCHITECTURE"
    assert roles["docs/product-work-map.yaml"] == "SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW"
    control_ref = "ops/hourly-github-relay-control:.agent/relay/work-claims.json"
    assert roles[control_ref] == "OPERATIONAL_EXECUTION_STATE_ONLY"


def test_transition_targets_beta_a_and_keeps_relay_disabled() -> None:
    spec = load_spec()
    transition = spec["transition_expectation"]
    assert transition["expected_items"]["beta_architecture"]["pr"] == 87
    assert transition["expected_items"]["m1c_migration_evidence"]["pr"] == 85
    assert transition["expected_items"]["ux_fp_fn_spec"]["pr"] == 63
    assert transition["expected_items"]["old_work_map_reconciliation"]["pr"] == 89
    assert transition["next_runtime_slice_after_beta_architecture_approval"] == "BETA-A"
    assert transition["scheduled_relay_must_remain_disabled"] is True


def test_consistency_and_relay_reenable_gates_fail_closed() -> None:
    spec = load_spec()
    invariants = spec["consistency_invariants"]
    assert invariants["authoritative_delivery_sources_max"] == 1
    assert invariants["critical_path_item_without_slice_mapping"] == 0
    assert invariants["ready_item_without_goal_spec_authority"] == 0
    assert invariants["claim_registry_product_priority_ownership"] == 0
    assert invariants["relay_selector_program_selector_disagreement"] == 0
    assert spec["relay_reenable_gate"]["spec_merge_enables_relay"] is False
    required = set(spec["relay_reenable_gate"]["required"])
    assert {
        "implementation_merged_to_main",
        "main_full_quality_green",
        "main_security_gates_green",
        "source_consistency_gate_green",
        "deterministic_selector_proof_green",
        "beta_a_selected_after_architecture_dependency_satisfied",
        "bounded_acceptance_run_green",
    } <= required


def test_spec_phase_forbids_control_plane_changes() -> None:
    spec = load_spec()
    forbidden = set(spec["spec_acceptance"]["forbidden_in_this_pr"])
    assert {
        "runtime_selector_change",
        "existing_ssot_authority_change",
        "relay_prompt_change",
        "scheduled_task_reenable",
        "product_runtime_implementation",
    } <= forbidden


def test_human_documents_define_split_brain_and_selector_proofs() -> None:
    spec_md = SPEC_MD.read_text(encoding="utf-8")
    threat_model = THREAT_MODEL.read_text(encoding="utf-8")
    test_design = TEST_DESIGN.read_text(encoding="utf-8")
    assert "SPEC-PROGRAM-DELIVERY-SSOT@1.0.0" in spec_md
    assert "what should be delivered next" in spec_md
    assert "Split-brain abuse case" in threat_model
    assert "Authority laundering abuse case" in threat_model
    assert "BETA-A selector acceptance" in test_design
    assert "Critical mutation survivors must be `0`" in test_design
