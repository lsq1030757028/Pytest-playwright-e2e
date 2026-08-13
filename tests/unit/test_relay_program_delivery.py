from copy import deepcopy
from pathlib import Path

import yaml

from test_workflow.relay_claims import select_work_item

PROGRAM_PATH = Path("docs/program-delivery-ssot.yaml")


def load_current_program() -> dict[str, object]:
    return yaml.safe_load(PROGRAM_PATH.read_text(encoding="utf-8"))


def registry(*claims: dict[str, object], claim_sequence: int = 0) -> dict[str, object]:
    return {
        "schema_version": 1,
        "control_id": "PARALLEL-WORK-CLAIMS",
        "enabled": True,
        "revision": 100,
        "claim_sequence": claim_sequence,
        "claims": {claim["work_item_id"]: claim for claim in claims},
        "recovered_claims": [],
        "integration_queue": [],
    }


def active_claim(
    work_item_id: str,
    *,
    domain: str,
    branch: str,
    target_pr: int | None = None,
) -> dict[str, object]:
    return {
        "work_item_id": work_item_id,
        "state": "IN_PROGRESS",
        "exclusive_domain": domain,
        "target_branch": branch,
        "target_pr": target_pr,
    }


def test_relay_selector_resolves_current_beta_a_acceptance() -> None:
    program = load_current_program()
    result = select_work_item(program, registry())
    assert result.work_item_id == "BETA-A-ACCEPTANCE"


def test_claim_sequence_cannot_reprioritize_program_delivery() -> None:
    program = load_current_program()
    low_sequence = select_work_item(program, registry(claim_sequence=1))
    high_sequence = select_work_item(program, registry(claim_sequence=1_000_000))
    assert low_sequence.work_item_id == "BETA-A-ACCEPTANCE"
    assert high_sequence.work_item_id == "BETA-A-ACCEPTANCE"


def test_unrelated_parallel_claim_does_not_displace_beta_a() -> None:
    program = load_current_program()
    state = registry(
        active_claim(
            "M1C-MEMORY-FORMATION-CLOSURE",
            domain="memory-formation",
            branch="fix/m1c-migration-evidence",
            target_pr=85,
        )
    )
    result = select_work_item(program, state)
    assert result.work_item_id == "BETA-A-ACCEPTANCE"


def test_claim_conflict_filters_candidate_without_changing_remaining_order() -> None:
    program = load_current_program()
    items = {item["work_item_id"]: item for item in program["work_items"]}
    horizontal = deepcopy(items["M1D-SHARED-MEMORY-GOVERNANCE"])
    horizontal.update(
        {
            "work_item_id": "READY-HORIZONTAL",
            "state": "READY",
            "priority": 99_999,
            "dependencies": [],
            "authority_issue": 95,
            "required_spec": "SPEC-BETA-A-DURABLE-GOVERNED-PACK@0.1.0",
            "target_branch": "horizontal",
            "target_pr": None,
            "exclusive_domain": "horizontal",
            "selection_class": "UNMAPPED_HORIZONTAL_INFRASTRUCTURE",
            "supports_slices": ["BETA-E"],
        }
    )
    program["work_items"].append(horizontal)

    state = registry(
        active_claim(
            "FOREIGN-BETA-A",
            domain="beta-a-runtime",
            branch="foreign-beta-a",
        )
    )
    result = select_work_item(program, state)
    assert result.work_item_id == "READY-HORIZONTAL"
    assert result.rejected["BETA-A-ACCEPTANCE"] == (
        "domain_conflict:beta-a-runtime"
    )
