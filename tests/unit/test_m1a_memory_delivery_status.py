from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
APPROVAL_PATH = ROOT / "docs/specs/m1a-memory-contracts-namespaces-approval.yaml"
LEDGER_PATH = ROOT / "docs/m1a-memory-contracts-delivery-ledger.yaml"
ROADMAP_PATH = ROOT / "docs/agent-os-roadmap.yaml"
STATUS_PATH = ROOT / "docs/implementation-status.md"
CLEANUP_PATH = ROOT / ".github/workflows/cleanup-implementation-branches.yml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_m1a_spec_delivery_is_closed_with_main_release_and_cleanup_evidence() -> None:
    approval = load_yaml(APPROVAL_PATH)
    ledger = load_yaml(LEDGER_PATH)

    assert approval["status"] == "APPROVED"
    assert ledger["status"] == "CLOSED"
    assert ledger["phase"] == "SPEC"
    assert ledger["profile"] == "DEV3"
    assert ledger["goal_issue"] == 28
    assert ledger["pull_request"] == 41
    assert ledger["merge_commit"] == "4cc4beb99fa9e45509ea1be240b0c2edebbe6137"
    assert ledger["verification"]["pr_spec_gate"]["result"] == "SUCCESS"
    assert ledger["verification"]["pr_full_quality"]["result"] == "SUCCESS"
    assert ledger["verification"]["main_spec_gate"]["result"] == "SUCCESS"
    assert ledger["verification"]["main_full_quality"]["result"] == "SUCCESS"
    assert ledger["verification"]["release"]["result"] == "SUCCESS"
    assert ledger["verification"]["cleanup"]["result"] == "SUCCESS"
    assert ledger["verification"]["review_threads"] == 0
    assert ledger["verification"]["cleanup"]["spec_branch_deleted"] is True


def test_m1a_closure_preserves_runtime_and_memory_gate_boundaries() -> None:
    ledger = load_yaml(LEDGER_PATH)
    roadmap = load_yaml(ROADMAP_PATH)
    status = STATUS_PATH.read_text(encoding="utf-8")

    assert ledger["protected_boundaries"]["runtime_store_implemented"] is False
    assert ledger["protected_boundaries"]["memory_gate_closed"] is False
    assert ledger["protected_boundaries"]["stage_delivery_ready"] is False
    assert ledger["protected_boundaries"]["production_data_or_secret_access"] is False
    assert ledger["protected_boundaries"]["oracle_policy_permission_changes"] is False
    assert ledger["next_state"]["module"] == "M1A_RUNTIME_CONTRACTS"
    assert ledger["next_state"]["m1b_status"] == (
        "BLOCKED_UNTIL_M1A_RUNTIME_CONTRACTS_VERIFIED"
    )
    assert roadmap["stage_delivery_status"] == "NOT_READY"
    assert roadmap["next_execution_sequence"][0] == "M1A_RUNTIME_CONTRACTS"
    assert "M1A Runtime Contracts：NEXT / DEV3" in status
    assert "M1B Store & Progressive Retrieval：BLOCKED" in status
    assert "M1 Memory Gate：0 / 1" in status
    assert "Stage Delivery：NOT_READY" in status


def test_closure_branch_is_registered_for_cleanup() -> None:
    cleanup = CLEANUP_PATH.read_text(encoding="utf-8")

    assert '"spec/m1a-memory-contracts-namespaces"' in cleanup
    assert '"docs/m1a-memory-contracts-final-ledger"' in cleanup
