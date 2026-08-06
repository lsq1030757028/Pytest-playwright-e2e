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


def test_live_status_records_merged_closed_runtime() -> None:
    ux_status = UX_STATUS_PATH.read_text(encoding="utf-8")
    project_status = PROJECT_STATUS_PATH.read_text(encoding="utf-8")

    assert "UX1 TodoMVC UX Mutation Proof SPEC：MERGED / CLOSED" in ux_status
    assert "UX1 Mutation Proof Runner：MERGED / CLOSED" in ux_status
    assert "Five-mutation Campaign：5 / 5 KILLED" in ux_status
    assert "Independent Replay：PASS / 100%" in ux_status
    assert "Critical False Green：0" in ux_status
    assert "UX False-positive / False-negative Benchmark：NEXT / SPEC" in ux_status

    assert "TodoMVC UX Mutation Proof SPEC：MERGED / CLOSED" in project_status
    assert "UX Mutation Proof Runner：MERGED / CLOSED" in project_status
    assert "Five-mutation Campaign：5 / 5 KILLED" in project_status
    assert "M1A Runtime Contracts：MERGED / CLOSED" in project_status
    assert "M1B Store & Progressive Retrieval：NEXT / SPEC" in project_status
    assert "M1 Memory Gate：0 / 1" in project_status
    assert "Stage Delivery：NOT_READY" in project_status


def test_ux1_ledger_binds_main_release_and_cleanup_evidence() -> None:
    module = ux1_module()
    evidence = module["test_evidence"]
    notes = "\n".join(module["notes"])

    assert module["status"] == "MERGED"
    assert module["branch"] == "main"
    assert module["pull_request"] == 37
    assert module["commit"] == "2b5bc958e5c302cef8649e28ff13d8ebafa3afcc"
    assert module["ci_run"] == 31002716954
    assert "10 focused Unit/Contract/Sandbox/Delivery PASS" in evidence[
        "unit_result"
    ]
    assert "5/5 real TodoMVC mutations KILLED" in evidence["integration_result"]
    assert "independent replay 100%" in evidence["integration_result"]
    assert "Critical False Green 0" in evidence["integration_result"]
    assert "github-actions-artifact:8929019254" in evidence["asset_paths"]
    assert "python-distribution-artifact:8928961328" in evidence["asset_paths"]
    assert "docker-build-record:8928992374" in evidence["asset_paths"]
    assert "Main UX1 Gate Run #17 / 31002717005 SUCCESS" in notes
    assert "Main Quality Run #174 / 31002716954 SUCCESS" in notes
    assert "Release Run #14 / 31002716980 SUCCESS" in notes
    assert "Cleanup Run #12 / 31002717017 SUCCESS" in notes
    assert "sha256:c7e5f7e9ce4e2190c7e043765b3176f" in notes
    assert "sha256:0ec56a6ca9f0b5f2c9b4564b5bc173df" in notes
    assert "sha256:34c8915bccb010a814b7783f43db25bc" in notes
    assert "implementation branch deleted" in notes


def test_runtime_document_and_cleanup_preserve_protected_boundaries() -> None:
    runtime_doc = RUNTIME_DOC_PATH.read_text(encoding="utf-8")
    cleanup = CLEANUP_PATH.read_text(encoding="utf-8")
    combined_status = (
        UX_STATUS_PATH.read_text(encoding="utf-8")
        + PROJECT_STATUS_PATH.read_text(encoding="utf-8")
        + runtime_doc
    )

    assert "MERGED / CLOSED" in runtime_doc
    assert "Main UX1 Gate：Run #17 / 31002717005 — SUCCESS" in runtime_doc
    assert "Real Mutation Campaign：5 / 5 KILLED" in runtime_doc
    assert "Independent Replay：100%" in runtime_doc
    assert "NONBLOCKING_SHADOW" in runtime_doc
    assert "Human UAT" in runtime_doc
    assert '"agent/ux1-todomvc-mutation-proof-runner"' in cleanup
    assert '"docs/ux1-mutation-final-ledger"' in cleanup
    assert "ADVISORY_ENABLED" not in combined_status
    assert "BLOCKING_ENABLED" not in combined_status
