from collections import defaultdict, deque
from pathlib import Path

import yaml

SPEC_PATH = Path("docs/specs/parallel-work-claims.yaml")
WORK_MAP_PATH = Path("docs/product-work-map.yaml")
SPEC_MD_PATH = Path("docs/specs/parallel-work-claims.md")
WORK_MAP_MD_PATH = Path("docs/product-work-map.md")
TEST_DESIGN_PATH = Path("docs/test-design/parallel-work-claims-test-design.md")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_parallel_claim_spec_has_owner_authority_and_no_m4_claim() -> None:
    spec = load_yaml(SPEC_PATH)
    assert spec["goal_issue"] == 55
    assert spec["parent_relay_issue"] == 49
    assert spec["authority"] == "OWNER-AUTH-PARALLEL-WORK-CLAIMS-M1-M3@1.0.0"
    assert spec["mandate"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert spec["classification"]["milestones_supported"] == ["M1", "M2", "M3"]
    assert spec["classification"]["product_m4_claim"] is False


def test_claiming_and_integration_fail_closed() -> None:
    spec = load_yaml(SPEC_PATH)
    assert spec["claiming"]["registry_cas"] == "required"
    assert spec["claiming"]["max_selection_retries_after_cas_conflict"] == 1
    assert spec["conflicts"]["duplicate_domain_active_claims_allowed"] is False
    assert spec["fencing"]["before_every_mutation"] is True
    assert spec["fencing"]["force_push_allowed"] is False
    assert spec["fencing"]["reset_allowed"] is False
    assert spec["integration"]["serialized"] is True
    assert spec["verification"]["parallelism_may_lower_evidence"] is False
    assert spec["verification"]["critical_false_green"] == 0


def test_work_items_have_unique_ids_and_required_contract() -> None:
    spec = load_yaml(SPEC_PATH)
    work_map = load_yaml(WORK_MAP_PATH)
    items = work_map["work_items"]
    required = set(spec["work_item"]["required_fields"])
    ids = [item["work_item_id"] for item in items]
    assert len(ids) == len(set(ids))
    assert ids
    for item in items:
        assert required <= set(item)
        assert item["exclusive_domain"]
        assert item["integration_group"] in work_map["integration_groups"]
        assert item["assurance"]["development"] in {"DEV0", "DEV1", "DEV2", "DEV3"}
        assert item["assurance"]["ux"] in {"UX0", "UX1", "UX2", "UX3"}


def test_dependencies_exist_and_are_acyclic() -> None:
    work_map = load_yaml(WORK_MAP_PATH)
    items = {item["work_item_id"]: item for item in work_map["work_items"]}
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


def test_current_business_dependencies_are_truthful() -> None:
    work_map = load_yaml(WORK_MAP_PATH)
    items = {item["work_item_id"]: item for item in work_map["work_items"]}
    assert items["M1A-RUNTIME-CONTRACTS-CLOSE"]["state"] == "READY"
    assert items["UX-FP-FN-BENCHMARK-SPEC"]["state"] == "READY"
    assert items["M1B-STORE-RETRIEVAL-SPEC"]["state"] == "BLOCKED"
    assert items["M1B-STORE-RETRIEVAL-SPEC"]["dependencies"] == ["M1A-RUNTIME-CONTRACTS-CLOSE"]
    assert items["M2A-MODEL-CAPABILITY-PROFILE"]["dependencies"] == ["M1F-MEMORY-GATE"]
    assert items["M3A-PROJECT-ARCHITECTURE-CONTRACTS"]["dependencies"] == ["M2E-ROUTING-ESCALATION"]
    assert "M4" not in {item["milestone"] for item in items.values()}


def test_integration_and_release_are_serialized_domains() -> None:
    spec = load_yaml(SPEC_PATH)
    work_map = load_yaml(WORK_MAP_PATH)
    always_serialized = set(spec["conflicts"]["always_serialized"])
    domains = {item["exclusive_domain"] for item in work_map["work_items"]}
    assert {"main_integration", "package_or_image_release"} <= always_serialized
    assert {"integration-main", "release-status"} <= domains
    assert work_map["domain_incompatibilities"]["integration-main"] == ["release-status"]
    assert work_map["domain_incompatibilities"]["release-status"] == ["integration-main"]


def test_human_documents_and_test_design_exist() -> None:
    spec_md = SPEC_MD_PATH.read_text(encoding="utf-8")
    work_map_md = WORK_MAP_MD_PATH.read_text(encoding="utf-8")
    test_design = TEST_DESIGN_PATH.read_text(encoding="utf-8")
    assert "SPEC-PARALLEL-WORK-CLAIMS@0.1.0" in spec_md
    assert "PRODUCT-WORK-MAP-M1-M3@0.1.0" in work_map_md
    assert "one CAS winner" in test_design
    assert "Critical False Green target: `0`" in test_design
