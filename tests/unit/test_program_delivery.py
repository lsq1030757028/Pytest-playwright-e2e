from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from test_workflow.program_delivery import (
    ProgramDeliveryError,
    load_program_delivery,
    select_next_work_item,
    validate_program_delivery,
)

SSOT_PATH = Path("docs/program-delivery-ssot.yaml")
HUMAN_PATH = Path("docs/program-delivery-ssot.md")


def load_raw() -> dict[str, object]:
    return yaml.safe_load(SSOT_PATH.read_text(encoding="utf-8"))


def items_by_id(data: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["work_item_id"]: item for item in data["work_items"]}


def close_governance_and_ready_beta_a(data: dict[str, object]) -> dict[str, object]:
    result = deepcopy(data)
    items = items_by_id(result)
    items["PROGRAM-DELIVERY-SSOT-IMPLEMENTATION"]["state"] = "CLOSED"
    items["BETA-A-SPEC"]["state"] = "READY"
    result["program"]["state"] = "PRE_BETA_A"
    result["execution_pointer"]["current_focus"] = "BETA-A-SPEC"
    result["execution_pointer"]["critical_path"] = [
        "BETA-A-SPEC",
        "BETA-A-IMPLEMENTATION",
        "BETA-A-ACCEPTANCE",
    ]
    return result


def test_canonical_program_delivery_ssot_validates() -> None:
    data = load_program_delivery(SSOT_PATH)
    assert data["program_delivery"]["source_role"] == "AUTHORITATIVE_DELIVERY"
    assert data["program"]["id"] == "TEST_AGENT_RUNTIME_BETA"
    assert data["program"]["state"] == "PRE_BETA_A"
    assert data["execution_pointer"]["active_slice"] == "BETA-A"
    assert data["execution_pointer"]["current_focus"] == "BETA-A-SPEC"
    assert data["relay_enablement"]["state"] == "DISABLED_GOVERNANCE_MIGRATION"


def test_current_closed_migration_selects_beta_a_spec() -> None:
    data = load_raw()
    items = items_by_id(data)
    assert data["program"]["state"] == "PRE_BETA_A"
    assert items["PROGRAM-DELIVERY-SSOT-IMPLEMENTATION"]["state"] == "CLOSED"
    assert items["BETA-A-SPEC"]["state"] == "READY"

    decision = select_next_work_item(data)
    assert decision.selected_work_item_id == "BETA-A-SPEC"
    assert decision.candidates[0] == "BETA-A-SPEC"


def test_after_governance_closure_selector_moves_to_beta_a_spec() -> None:
    data = close_governance_and_ready_beta_a(load_raw())
    validate_program_delivery(data)
    decision = select_next_work_item(data)
    assert decision.selected_work_item_id == "BETA-A-SPEC"
    assert decision.candidates[0] == "BETA-A-SPEC"


def test_security_correctness_repair_outranks_beta_a() -> None:
    data = close_governance_and_ready_beta_a(load_raw())
    data["work_items"].append(
        {
            "work_item_id": "SECURITY-REPAIR",
            "outcome": "repair a proven security gate defect",
            "state": "READY",
            "phase": "IMPLEMENTATION",
            "selection_class": "SECURITY_CORRECTNESS_REPAIR",
            "priority": 1,
            "dependencies": [],
            "authority_issue": 91,
            "required_spec": "SPEC-PROGRAM-DELIVERY-SSOT@1.0.0",
            "target_branch": None,
            "target_pr": None,
            "exclusive_domain": "security-repair",
            "blocks_slice": "BETA-A",
            "supports_slices": ["BETA-A"],
            "completion_checks": ["security_gate_green"],
        }
    )
    decision = select_next_work_item(data)
    assert decision.selected_work_item_id == "SECURITY-REPAIR"


def test_unmapped_horizontal_infrastructure_cannot_jump_beta_a_queue() -> None:
    data = close_governance_and_ready_beta_a(load_raw())
    data["work_items"].append(
        {
            "work_item_id": "ATTRACTIVE-HORIZONTAL-INFRA",
            "outcome": "build infrastructure not needed by active slice",
            "state": "READY",
            "phase": "SPEC",
            "selection_class": "UNMAPPED_HORIZONTAL_INFRASTRUCTURE",
            "priority": 999999,
            "dependencies": [],
            "authority_issue": 91,
            "required_spec": "self",
            "target_branch": None,
            "target_pr": None,
            "exclusive_domain": "future-infra",
            "supports_slices": ["BETA-D"],
            "completion_checks": ["future_only"],
        }
    )
    decision = select_next_work_item(data)
    assert decision.selected_work_item_id == "BETA-A-SPEC"


def test_execution_ownership_only_removes_candidate_not_product_truth() -> None:
    data = close_governance_and_ready_beta_a(load_raw())
    before = deepcopy(items_by_id(data)["BETA-A-SPEC"])
    decision = select_next_work_item(
        data, unavailable_work_item_ids={"BETA-A-SPEC"}
    )
    after = items_by_id(data)["BETA-A-SPEC"]
    assert before == after
    assert after["state"] == "READY"
    assert decision.selected_work_item_id is None
    assert (
        "BETA-A-SPEC",
        "execution_ownership_unavailable",
    ) in decision.excluded


def test_ready_work_requires_authority_and_spec() -> None:
    data = close_governance_and_ready_beta_a(load_raw())
    items_by_id(data)["BETA-A-SPEC"]["authority_issue"] = None
    with pytest.raises(ProgramDeliveryError, match="lacks authority/spec"):
        validate_program_delivery(data)


def test_ready_work_cannot_have_open_dependency() -> None:
    data = deepcopy(load_raw())
    items = items_by_id(data)
    items["PROGRAM-DELIVERY-SSOT-IMPLEMENTATION"]["state"] = "IN_PROGRESS"
    items["BETA-A-SPEC"]["state"] = "READY"
    with pytest.raises(ProgramDeliveryError, match="open dependency"):
        validate_program_delivery(data)


def test_critical_path_work_requires_slice_mapping() -> None:
    data = deepcopy(load_raw())
    item = items_by_id(data)["BETA-A-SPEC"]
    item.pop("blocks_slice")
    with pytest.raises(ProgramDeliveryError, match="lacks product mapping"):
        validate_program_delivery(data)


def test_claim_registry_is_operational_only() -> None:
    data = load_raw()
    role = data["source_roles"][
        "ops/hourly-github-relay-control:.agent/relay/work-claims.json"
    ]
    assert role["role"] == "OPERATIONAL_EXECUTION_STATE_ONLY"
    assert role["may_select_next_work"] is False


def test_only_canonical_yaml_may_select_next_work() -> None:
    data = load_raw()
    selectors = [
        path
        for path, role in data["source_roles"].items()
        if role["may_select_next_work"]
    ]
    assert selectors == ["docs/program-delivery-ssot.yaml"]


def test_human_companion_matches_current_pointer() -> None:
    data = load_raw()
    text = HUMAN_PATH.read_text(encoding="utf-8")
    assert f"Product: {data['program']['id']}" in text
    assert f"Program State: {data['program']['state']}" in text
    assert f"Active Slice: {data['execution_pointer']['active_slice']}" in text
    assert f"Current Focus: {data['execution_pointer']['current_focus']}" in text
    assert (
        f"Next Slice After Active: {data['execution_pointer']['next_slice_after_active']}"
        in text
    )


def test_milestone_and_claim_sequence_are_forbidden_priority_signals() -> None:
    data = load_raw()
    forbidden = set(data["selection_policy"]["forbidden_priority_signals"])
    assert "milestone_number" in forbidden
    assert "claim_registry_sequence" in forbidden
