from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from test_workflow.program_delivery import (
    ProgramDeliveryError,
    select_next_work_item,
    validate_program_delivery,
)

SSOT_PATH = Path("docs/program-delivery-ssot.yaml")


def load_raw() -> dict[str, object]:
    return yaml.safe_load(SSOT_PATH.read_text(encoding="utf-8"))


def items_by_id(data: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["work_item_id"]: item for item in data["work_items"]}


def test_mutant_second_authoritative_delivery_source_is_killed() -> None:
    data = deepcopy(load_raw())
    legacy = data["source_roles"]["docs/product-work-map.yaml"]
    legacy["role"] = "AUTHORITATIVE_DELIVERY"
    legacy["may_select_next_work"] = True
    with pytest.raises(ProgramDeliveryError, match="exactly docs/program-delivery"):
        validate_program_delivery(data)


def test_mutant_claim_registry_product_selector_is_killed() -> None:
    data = deepcopy(load_raw())
    claim_role = data["source_roles"][
        "ops/hourly-github-relay-control:.agent/relay/work-claims.json"
    ]
    claim_role["may_select_next_work"] = True
    with pytest.raises(ProgramDeliveryError, match="non-authoritative source may select work"):
        validate_program_delivery(data)


def test_mutant_critical_path_without_slice_mapping_is_killed() -> None:
    data = deepcopy(load_raw())
    item = items_by_id(data)["BETA-A-ACCEPTANCE"]
    item.pop("closes_slice")
    with pytest.raises(ProgramDeliveryError, match="lacks product mapping"):
        validate_program_delivery(data)


def test_mutant_security_repair_not_first_is_killed() -> None:
    data = deepcopy(load_raw())
    classes = data["selection_policy"]["classes_in_order"]
    classes[0], classes[1] = classes[1], classes[0]
    with pytest.raises(ProgramDeliveryError, match="security/correctness repair must be first"):
        validate_program_delivery(data)


def test_mutant_unmapped_horizontal_not_last_is_killed() -> None:
    data = deepcopy(load_raw())
    classes = data["selection_policy"]["classes_in_order"]
    classes[-1], classes[-2] = classes[-2], classes[-1]
    with pytest.raises(
        ProgramDeliveryError,
        match="unmapped horizontal infrastructure must be last",
    ):
        validate_program_delivery(data)


def test_mutant_ready_without_authority_is_killed() -> None:
    data = deepcopy(load_raw())
    items_by_id(data)["BETA-A-ACCEPTANCE"]["authority_issue"] = None
    with pytest.raises(ProgramDeliveryError, match="lacks authority/spec"):
        validate_program_delivery(data)


def test_mutant_unknown_slice_dependency_is_killed() -> None:
    data = deepcopy(load_raw())
    data["product_slices"]["BETA-B"]["dependencies"] = ["BETA-Z"]
    with pytest.raises(ProgramDeliveryError, match="unknown slice dependency"):
        validate_program_delivery(data)


def test_mutant_cyclic_slice_dependency_is_killed() -> None:
    data = deepcopy(load_raw())
    data["product_slices"]["BETA-A"]["dependencies"] = ["BETA-E"]
    with pytest.raises(ProgramDeliveryError, match="contains a cycle"):
        validate_program_delivery(data)


def test_mutant_milestone_priority_signal_is_killed() -> None:
    data = deepcopy(load_raw())
    data["selection_policy"]["forbidden_priority_signals"].remove("milestone_number")
    with pytest.raises(ProgramDeliveryError, match="forbidden priority signals are incomplete"):
        validate_program_delivery(data)


def test_claim_ownership_cannot_mutate_product_readiness() -> None:
    data = deepcopy(load_raw())
    before = deepcopy(items_by_id(data)["BETA-A-ACCEPTANCE"])
    decision = select_next_work_item(
        data, unavailable_work_item_ids={"BETA-A-ACCEPTANCE"}
    )
    after = items_by_id(data)["BETA-A-ACCEPTANCE"]
    assert after == before
    assert after["state"] == "READY"
    assert decision.selected_work_item_id is None


def test_active_slice_selector_cannot_fall_through_to_future_horizontal() -> None:
    data = deepcopy(load_raw())
    items = items_by_id(data)
    items["M1D-SHARED-MEMORY-GOVERNANCE"]["state"] = "READY"
    items["M1C-MEMORY-FORMATION-CLOSURE"]["state"] = "CLOSED"
    items["M1D-SHARED-MEMORY-GOVERNANCE"]["authority_issue"] = 74
    decision = select_next_work_item(data)
    assert decision.selected_work_item_id == "BETA-A-ACCEPTANCE"
    assert decision.candidates.index("BETA-A-ACCEPTANCE") < decision.candidates.index(
        "M1D-SHARED-MEMORY-GOVERNANCE"
    )
