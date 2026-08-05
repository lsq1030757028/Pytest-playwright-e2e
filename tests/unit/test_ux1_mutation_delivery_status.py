from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / "docs/implementation-ledger.yaml"
UX_STATUS_PATH = ROOT / "docs/ux-assurance-status.md"
PROJECT_STATUS_PATH = ROOT / "docs/implementation-status.md"
RUNTIME_DOC_PATH = ROOT / "docs/ux1-todomvc-mutation-proof-runtime.md"
CLEANUP_PATH = ROOT / ".github/workflows/cleanup-implementation-branches.yml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def ux1_module() -> dict[str, object]:
    ledger = load_yaml(LEDGER_PATH)
    return next(
        module
        for module in ledger["modules"]
        if module["module_id"] == "ux1-todomvc-mutation-proof-runner"
    )


def test_live_status_records_verified_merge_pending_runtime() -> None:
    ux_status = UX_STATUS_PATH.read_text(encoding="utf-8")
    project_status = PROJECT_STATUS_PATH.read_text(encoding="utf-8")

    assert "UX1 TodoMVC UX Mutation Proof：SPEC MERGED / CLOSED" in ux_status
    assert "UX Mutation Proof Runner：VERIFIED / MERGE_PENDING" in ux_status
    assert "Five-mutation Campaign：5 / 5 KILLED" in ux_status
    assert "Independent Replay：PASS / 100%" in ux_status
    assert "Critical False Green：0" in ux_status

    assert "TodoMVC UX Mutation Proof：SPEC MERGED / CLOSED" in project_status
    assert "UX Mutation Proof Runner：VERIFIED / MERGE_PENDING" in project_status
    assert "Five-mutation Campaign：5 / 5 KILLED" in project_status
    assert "M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT" in project_status
    assert "M1 Memory Gate：0 / 1" in project_status
    assert "Stage Delivery：NOT_READY" in project_status


def test_ux1_ledger_binds_pr_evidence_without_claiming_merge() -> None:
    module = ux1_module()
    evidence = module["test_evidence"]
    notes = "\n".join(module["notes"])

    assert module["status"] == "VERIFIED"
    assert module["branch"] == "agent/ux1-todomvc-mutation-proof-runner"
    assert module["pull_request"] == 37
    assert module["ci_run"] == 31001744148
    assert "7 focused Unit/Contract/Sandbox/State-machine PASS" in evidence[
        "unit_result"
    ]
    assert "5/5 real TodoMVC mutations KILLED" in evidence["integration_result"]
    assert "independent replay 100%" in evidence["integration_result"]
    assert "Critical False Green 0" in evidence["integration_result"]
    assert "github-actions-artifact:8928601100" in evidence["asset_paths"]
    assert "sha256:17a9ba0146a0acb8bc3ddf0a485be016" in notes
    assert "sha256:c0cfca3acd6c0f9b97575af221e44aa2" in notes
    assert "sha256:a0620348d61622cac018c4c766fc699a" in notes
    assert "Main, release and implementation-branch cleanup remain pending" in notes


def test_runtime_document_and_cleanup_preserve_protected_boundaries() -> None:
    runtime_doc = RUNTIME_DOC_PATH.read_text(encoding="utf-8")
    cleanup = CLEANUP_PATH.read_text(encoding="utf-8")
    combined_status = (
        UX_STATUS_PATH.read_text(encoding="utf-8")
        + PROJECT_STATUS_PATH.read_text(encoding="utf-8")
        + runtime_doc
    )

    assert "VERIFIED / MERGE_PENDING" in runtime_doc
    assert "Focused UX1 Gate：Run #10 / 31001744148 — SUCCESS" in runtime_doc
    assert "Real Mutation Campaign：5 / 5 KILLED" in runtime_doc
    assert "Independent Replay：100%" in runtime_doc
    assert "NONBLOCKING_SHADOW" in runtime_doc
    assert "Human UAT" in runtime_doc
    assert '"agent/ux1-todomvc-mutation-proof-runner"' in cleanup
    assert "ADVISORY_ENABLED" not in combined_status
    assert "BLOCKING_ENABLED" not in combined_status
