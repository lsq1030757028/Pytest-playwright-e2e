from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
APPROVAL_PATH = ROOT / "docs/specs/m1a-memory-contracts-namespaces-approval.yaml"
LEDGER_PATH = ROOT / "docs/m1a-memory-contracts-delivery-ledger.yaml"
RUNTIME_LEDGER_PATH = ROOT / "docs/m1a-memory-runtime-contracts-delivery-ledger.yaml"
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


def test_m1a_runtime_delivery_is_closed_without_claiming_a_production_store() -> None:
    ledger = load_yaml(RUNTIME_LEDGER_PATH)

    assert ledger["status"] == "CLOSED"
    assert ledger["phase"] == "IMPLEMENTATION"
    assert ledger["profile"] == "DEV3"
    assert ledger["goal_issue"] == 43
    assert ledger["pull_request"] == 44
    assert ledger["merge_commit"] == "0585e357aebda650ee50ee95ff962b3ac81f6d4c"
    assert ledger["verification"]["pr_runtime_gate"]["result"] == "SUCCESS"
    assert ledger["verification"]["main_runtime_gate"]["result"] == "SUCCESS"
    assert ledger["verification"]["main_full_quality"]["result"] == "SUCCESS"
    assert ledger["verification"]["release"]["result"] == "SUCCESS"
    assert ledger["verification"]["cleanup"]["result"] == "SUCCESS"
    assert ledger["verification"]["review_threads"] == 0
    assert ledger["verification"]["focused_tests"] == {"total": 29, "passed": 29}
    assert ledger["verification"]["deterministic_proof_scenarios"] == {
        "total": 15,
        "passed": 15,
    }
    assert ledger["verification"]["critical_false_green"] == 0
    assert ledger["verification"]["unauthorized_namespace_actions"] == 0
    assert ledger["verification"]["unauthorized_promotion_actions"] == 0
    assert ledger["verification"]["cleanup"]["implementation_branch_deleted"] is True
    assert ledger["closure_chain"]["closure_remediation_pr"] == 45
    assert ledger["closure_chain"]["closure_remediation_merge_commit"] == "ef681c3b679305d7b88d17f776926dc25b76e49f"
    assert ledger["closure_chain"]["integration_secret_scan_repair_pr"] == 61
    assert ledger["closure_chain"]["final_main_head"] == "bd673cb1cab3edc6d16eca2aded4dcfe4bd45957"
    assert ledger["verification"]["pr_runtime_gate"]["run_id"] == 31107607723
    assert ledger["verification"]["main_runtime_gate"]["run_id"] == 31108111384
    assert ledger["verification"]["main_full_quality"]["run_id"] == 31108781025
    assert ledger["verification"]["main_secret_scan"]["run_id"] == 31108779724
    assert ledger["verification"]["main_codeql"]["run_id"] == 31108779549
    assert ledger["verification"]["release"]["run_id"] == 31108779552
    assert ledger["verification"]["cleanup"]["repository_cleanup_run_id"] == 31108781076
    assert ledger["protected_boundaries"]["production_store_implemented"] is False
    assert ledger["protected_boundaries"]["database_or_vector_backend_selected"] is False
    assert ledger["protected_boundaries"]["memory_gate_closed"] is False
    assert ledger["protected_boundaries"]["stage_delivery_ready"] is False


def test_current_truth_advances_to_m1b_spec_and_preserves_global_boundaries() -> None:
    runtime_ledger = load_yaml(RUNTIME_LEDGER_PATH)
    roadmap = load_yaml(ROADMAP_PATH)
    status = STATUS_PATH.read_text(encoding="utf-8")

    assert runtime_ledger["next_state"]["module"] == (
        "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    )
    assert runtime_ledger["next_state"]["status"] == "NEXT"
    assert runtime_ledger["next_state"]["goal_issue"] == 62
    assert runtime_ledger["next_state"]["implementation_blocked_until_spec_approved"] is True
    assert roadmap["stage_delivery_status"] == "NOT_READY"
    assert roadmap["active_module"] == "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    assert roadmap["next_execution_sequence"][0] == (
        "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    )
    assert "M1A Runtime Contracts：MERGED / CLOSED" in status
    assert "M1B Store & Progressive Retrieval：NEXT / SPEC" in status
    assert "M1 Memory Gate：0 / 1" in status
    assert "Stage Delivery：NOT_READY" in status


def test_closure_and_probe_branches_are_registered_for_cleanup() -> None:
    cleanup = CLEANUP_PATH.read_text(encoding="utf-8")

    assert '"spec/m1a-memory-contracts-namespaces"' in cleanup
    assert '"docs/m1a-memory-contracts-final-ledger"' in cleanup
    assert '"docs/m1a-runtime-contracts-final-ledger"' in cleanup
    assert '"ops/m1a-runtime-closure-evidence"' in cleanup
    assert '"agent/m1a-runtime-contract-remediation"' in cleanup
    assert '"fix/m1a-integration-token-fingerprint"' in cleanup
