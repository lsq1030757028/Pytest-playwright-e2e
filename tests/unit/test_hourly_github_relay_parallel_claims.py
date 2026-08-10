from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs" / "specs"
PARALLEL_ADDENDUM = "ADDENDUM-HOURLY-GITHUB-RELAY-PARALLEL-CLAIMS@0.2.0"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def work_item(work_map: dict, work_item_id: str) -> dict:
    return next(
        item for item in work_map["work_items"] if item["work_item_id"] == work_item_id
    )


def test_parallel_claim_addendum_is_in_effective_protocol() -> None:
    base_markdown = (SPEC_DIR / "hourly-github-relay.md").read_text(encoding="utf-8")
    base_yaml = load_yaml(SPEC_DIR / "hourly-github-relay.yaml")
    addendum = load_yaml(SPEC_DIR / "hourly-github-relay-parallel-claims.yaml")

    assert PARALLEL_ADDENDUM in base_markdown
    assert PARALLEL_ADDENDUM in base_yaml["effective_protocol"]["addenda"]
    assert addendum["addendum_id"] == PARALLEL_ADDENDUM
    assert addendum["status"] == "OWNER_ACCEPTED_ACTIVATION_GATED"
    assert addendum["integration"]["module_claim_authorizes_merge"] is False
    assert addendum["compatibility_lease"]["ordinary_module_work_acquires"] is False


def test_runtime_bootstrap_separates_program_delivery_from_claim_ownership() -> None:
    prompt = (SPEC_DIR / "hourly-github-relay-prompt.md").read_text(encoding="utf-8")

    required = {
        "execution_profile: PARALLEL_WORK_CLAIMS",
        "docs/program-delivery-ssot.yaml",
        ".agent/relay/work-claims.json",
        ".agent/relay/leases/integration.json",
        "SHOULD_DO_NEXT",
        "WHO_DOES_IT",
        "resume it",
        "Different non-conflicting Work Items may run concurrently",
        "SESSION_ISOLATION_FAILED",
    }
    assert all(value in prompt for value in required)
    assert "SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW" in prompt
    assert "must never select or reorder work" in prompt
    assert "cannot make a blocked Work Item ready" in prompt
    assert "A Work Item claim alone never authorizes integration or product closure" in prompt


def test_foundation_work_items_are_closed_before_activation() -> None:
    work_map = load_yaml(ROOT / "docs" / "product-work-map.yaml")
    spec_item = work_item(work_map, "PARALLEL-WORK-CLAIMS-SPEC")
    implementation_item = work_item(work_map, "PARALLEL-WORK-CLAIMS-IMPLEMENTATION")
    relay_item = work_item(work_map, "RELAY-CONVERSATION-ISOLATION-CLOSE")

    assert spec_item["state"] == "CLOSED"
    assert spec_item["target_pr"] == 56
    assert implementation_item["state"] == "CLOSED"
    assert implementation_item["target_pr"] == 57
    assert relay_item["state"] == "IN_PROGRESS"


def test_parallel_claim_runtime_foundation_is_present() -> None:
    required_paths = [
        ROOT / "src" / "test_workflow" / "relay_claims.py",
        ROOT / ".agent" / "relay" / "schemas" / "work-claims.schema.json",
        ROOT / ".agent" / "relay" / "schemas" / "integration-lease.schema.json",
    ]
    assert all(path.is_file() for path in required_paths)
