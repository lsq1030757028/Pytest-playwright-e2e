from pathlib import Path

import yaml

PROGRAM_YAML = Path("docs/program-delivery-ssot.yaml")
AGENTS = Path("AGENTS.md")
DEVELOPMENT_MD = Path("docs/github-development-ssot.md")
DEVELOPMENT_YAML = Path("docs/github-development-ssot.yaml")
IMPLEMENTATION_STATUS = Path("docs/implementation-status.md")
ARCHITECTURE_ROADMAP = Path("docs/agent-os-roadmap.yaml")
EVOLUTION_ROADMAP = Path("docs/agent-os-evolution-roadmap.md")
PRODUCT_WORK_MAP = Path("docs/product-work-map.yaml")
PRODUCT_WORK_MAP_MD = Path("docs/product-work-map.md")
BETA_ROADMAP = Path("docs/test-agent-runtime-beta-roadmap.yaml")
PARALLEL_MD = Path("docs/specs/parallel-work-claims.md")
PARALLEL_YAML = Path("docs/specs/parallel-work-claims.yaml")
RELAY_PROMPT = Path("docs/specs/hourly-github-relay-prompt.md")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_program_delivery_is_the_only_delivery_selector_source() -> None:
    program = load_yaml(PROGRAM_YAML)
    selectors = [
        path
        for path, role in program["source_roles"].items()
        if role["may_select_next_work"]
    ]
    assert selectors == ["docs/program-delivery-ssot.yaml"]


def test_agents_reads_program_delivery_before_status_and_roadmap() -> None:
    text = AGENTS.read_text(encoding="utf-8")
    canonical = text.index("docs/program-delivery-ssot.yaml")
    status = text.index("docs/implementation-status.md")
    roadmap = text.index("docs/agent-os-evolution-roadmap.md")
    assert canonical < status
    assert canonical < roadmap
    assert "SHOULD_DO_NEXT" in text
    assert "WHO_DOES_IT" in text
    assert "REPLAN_REQUIRED" in text


def test_development_ssot_separates_authorization_and_delivery() -> None:
    data = load_yaml(DEVELOPMENT_YAML)
    assert data["entrypoints"]["program_delivery"] == "docs/program-delivery-ssot.yaml"
    selection = data["delivery_selection"]
    assert selection["authoritative_source"] == "docs/program-delivery-ssot.yaml"
    assert selection["claim_registry_may_define_product_priority"] is False
    assert selection["conflict_action"] == "REPLAN_REQUIRED"
    authorization = data["authorization"]
    assert authorization["delivery_ssot_may_expand_authority"] is False

    text = DEVELOPMENT_MD.read_text(encoding="utf-8")
    assert "MAY_DO" in text
    assert "SHOULD_DO_NEXT" in text
    assert "WHO_DOES_IT" in text
    assert "docs/program-delivery-ssot.yaml" in text


def test_parallel_claims_consumes_program_delivery_not_product_work_map() -> None:
    data = load_yaml(PARALLEL_YAML)
    assert data["sources"]["program_delivery"] == "docs/program-delivery-ssot.yaml"
    assert data["sources"]["product_work_map_role"] == "SUPERSEDED_COMPATIBILITY_VIEW"
    selection = data["claiming"]["selection"]
    assert selection["delivery_order_source"] == "docs/program-delivery-ssot.yaml"
    assert selection["claim_registry_may_change_product_priority"] is False

    text = PARALLEL_MD.read_text(encoding="utf-8")
    assert "Program Delivery SSOT" in text
    assert "OPERATIONAL_EXECUTION_STATE_ONLY" in text


def test_relay_prompt_uses_program_delivery_and_rejects_old_map_authority() -> None:
    text = RELAY_PROMPT.read_text(encoding="utf-8")
    assert "docs/program-delivery-ssot.yaml" in text
    assert "AUTHORITATIVE_DELIVERY" in text
    assert "docs/product-work-map.yaml" in text
    assert "SUPERSEDED" in text or "compatibility" in text.lower()
    assert "SHOULD_DO_NEXT" in text
    assert "WHO_DOES_IT" in text


def test_old_sources_are_explicitly_non_authoritative() -> None:
    status = IMPLEMENTATION_STATUS.read_text(encoding="utf-8")
    assert "Source Role: `GENERATED_VIEW`" in status
    assert "Delivery Selection Authoritative: `false`" in status

    architecture = load_yaml(ARCHITECTURE_ROADMAP)
    assert architecture["source_role"] == "REFERENCE_ARCHITECTURE"
    assert architecture["delivery_selection_authoritative"] is False
    assert "next_execution_sequence" not in architecture

    evolution = EVOLUTION_ROADMAP.read_text(encoding="utf-8")
    assert "Source Role: `REFERENCE_ARCHITECTURE_AND_RESEARCH`" in evolution
    assert "Delivery Selection Authoritative: `false`" in evolution

    work_map = load_yaml(PRODUCT_WORK_MAP)
    assert work_map["source_role"] == "SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW"
    assert work_map["delivery_selection_authoritative"] is False
    assert work_map["superseded_by"] == "docs/program-delivery-ssot.yaml"

    work_map_md = PRODUCT_WORK_MAP_MD.read_text(encoding="utf-8")
    assert "SUPERSEDED_DELIVERY_MAP_OR_COMPATIBILITY_VIEW" in work_map_md
    assert "docs/program-delivery-ssot.yaml" in work_map_md

    beta = load_yaml(BETA_ROADMAP)
    assert beta["source_role"] == "APPROVED_PRODUCT_SLICE_INPUT"
    assert beta["delivery_selection_authoritative"] is False
    assert beta["canonical_delivery_ssot"] == "docs/program-delivery-ssot.yaml"


def test_no_legacy_source_claims_delivery_authority() -> None:
    program = load_yaml(PROGRAM_YAML)
    legacy_paths = [
        "docs/implementation-status.md",
        "docs/agent-os-roadmap.yaml",
        "docs/agent-os-evolution-roadmap.md",
        "docs/product-work-map.yaml",
        "docs/test-agent-runtime-beta-roadmap.yaml",
    ]
    for path in legacy_paths:
        assert program["source_roles"][path]["may_select_next_work"] is False
