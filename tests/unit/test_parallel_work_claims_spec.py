from collections import defaultdict, deque
from pathlib import Path

import yaml

SPEC_PATH = Path("docs/specs/parallel-work-claims.yaml")
PROGRAM_PATH = Path("docs/program-delivery-ssot.yaml")
WORK_MAP_PATH = Path("docs/product-work-map.yaml")
SPEC_MD_PATH = Path("docs/specs/parallel-work-claims.md")
WORK_MAP_MD_PATH = Path("docs/product-work-map.md")
TEST_DESIGN_PATH = Path("docs/test-design/parallel-work-claims-test-design.md")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_parallel_claim_spec_preserves_mandate_boundary_and_explicit_authority() -> None:
    spec = load_yaml(SPEC_PATH)
    assert spec["goal_issue"] == 55
    assert spec["parent_relay_issue"] == 49
    assert spec["authority"] == "OWNER-AUTH-PARALLEL-WORK-CLAIMS-M1-M3@1.0.0"
    assert spec["mandate"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert spec["delivery_selection_contract"] == "SPEC-PROGRAM-DELIVERY-SSOT@1.0.0"
    assert spec["classification"]["standing_mandate_milestones"] == ["M1", "M2", "M3"]
    assert spec["classification"]["product_m4_claim"] is False
    assert spec["classification"]["explicit_owner_authority_items_allowed"] is True
    assert spec["classification"]["explicit_owner_authority_does_not_expand_mandate"] is True


def test_claiming_and_integration_fail_closed() -> None:
    spec = load_yaml(SPEC_PATH)
    selection = spec["claiming"]["selection"]
    assert spec["claiming"]["registry_cas"] == "required"
    assert spec["claiming"]["max_selection_retries_after_cas_conflict"] == 1
    assert selection["delivery_order_source"] == "docs/program-delivery-ssot.yaml"
    assert selection["authorization_evaluated_separately"] == "required"
    assert selection["claim_registry_may_change_product_priority"] is False
    assert selection["claim_registry_may_change_product_readiness"] is False
    assert selection["claim_registry_only_filters_execution_ownership"] is True
    assert spec["conflicts"]["duplicate_domain_active_claims_allowed"] is False
    assert spec["fencing"]["before_every_mutation"] is True
    assert spec["fencing"]["force_push_allowed"] is False
    assert spec["fencing"]["reset_allowed"] is False
    assert spec["integration"]["serialized"] is True
    assert spec["verification"]["parallelism_may_lower_evidence"] is False
    assert spec["verification"]["critical_false_green"] == 0


def test_program_delivery_work_items_have_unique_ids_and_claim_contract() -> None:
    spec = load_yaml(SPEC_PATH)
    program = load_yaml(PROGRAM_PATH)
    items = program["work_items"]
    required = set(spec["work_item"]["required_for_claimable_item"])
    ids = [item["work_item_id"] for item in items]
    assert len(ids) == len(set(ids))
    assert ids
    claimable_states = set(program["selection_policy"]["claimable_states"])
    for item in items:
        assert item["work_item_id"]
        assert item["exclusive_domain"]
        if item["state"] in claimable_states:
            assert required <= set(item)
            assert item["authority_issue"]
            assert item["required_spec"]


def test_program_delivery_work_dependencies_exist_and_are_acyclic() -> None:
    program = load_yaml(PROGRAM_PATH)
    items = {item["work_item_id"]: item for item in program["work_items"]}
    incoming = {item_id: 0 for item_id in items}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for item_id, item in items.items():
        for dependency in item["dependencies"]:
            assert dependency in items
            outgoing[dependency].append(item_id)
            incoming[item_id] += 1
    queue = deque(sorted(item_id for item_id, count in incoming.items() if count == 0))
    visited: list[str] = []
    while queue:
        item_id = queue.popleft()
        visited.append(item_id)
        for child in outgoing[item_id]:
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    assert len(visited) == len(items)


def test_current_product_truth_comes_from_program_delivery() -> None:
    program = load_yaml(PROGRAM_PATH)
    items = {item["work_item_id"]: item for item in program["work_items"]}
    pointer = program["execution_pointer"]
    assert program["program"]["state"] == "PRE_BETA_A"
    assert pointer["active_slice"] == "BETA-A"
    assert pointer["current_focus"] == "BETA-A-SPEC"
    assert pointer["critical_path"][:2] == [
        "BETA-A-SPEC",
        "BETA-A-IMPLEMENTATION",
    ]
    assert items["PROGRAM-DELIVERY-SSOT-IMPLEMENTATION"]["state"] == "CLOSED"
    assert items["PROGRAM-DELIVERY-SSOT-IMPLEMENTATION"]["blocks_slice"] == "BETA-A"
    assert items["BETA-A-SPEC"]["state"] == "READY"
    assert items["BETA-A-SPEC"]["dependencies"] == [
        "PROGRAM-DELIVERY-SSOT-IMPLEMENTATION"
    ]
    assert items["M1C-MEMORY-FORMATION-CLOSURE"]["supports_slices"] == ["BETA-D"]
    assert items["UX-FP-FN-BENCHMARK-SPEC"]["supports_slices"] == [
        "BETA-C",
        "BETA-E",
    ]


def test_legacy_product_work_map_is_compatibility_only() -> None:
    spec = load_yaml(SPEC_PATH)
    work_map = load_yaml(WORK_MAP_PATH)
    assert spec["sources"]["program_delivery"] == "docs/program-delivery-ssot.yaml"
    assert spec["sources"]["product_work_map_role"] == "SUPERSEDED_COMPATIBILITY_VIEW"
    assert spec["sources"]["product_work_map_may_select_next_work"] is False
    assert work_map["status"] == "SUPERSEDED"
    assert work_map["source_role"] == "SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW"
    assert work_map["delivery_selection_authoritative"] is False
    assert work_map["superseded_by"] == "docs/program-delivery-ssot.yaml"


def test_integration_and_release_remain_serialized() -> None:
    spec = load_yaml(SPEC_PATH)
    always_serialized = set(spec["conflicts"]["always_serialized"])
    assert {"main_integration", "package_or_image_release"} <= always_serialized
    assert "program_delivery_closure" in always_serialized
    assert spec["integration"]["serialized"] is True
    assert spec["integration"]["integration_may_change_product_truth_directly"] is False
    assert spec["integration"]["post_integration_product_state_source"] == (
        "docs/program-delivery-ssot.yaml"
    )


def test_human_documents_and_test_design_exist() -> None:
    spec_md = SPEC_MD_PATH.read_text(encoding="utf-8")
    work_map_md = WORK_MAP_MD_PATH.read_text(encoding="utf-8")
    test_design = TEST_DESIGN_PATH.read_text(encoding="utf-8")
    assert "SPEC-PARALLEL-WORK-CLAIMS@0.1.0" in spec_md
    assert "Program Delivery SSOT" in spec_md
    assert "SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW" in work_map_md
    assert "one CAS winner" in test_design
    assert "Critical False Green target: `0`" in test_design
