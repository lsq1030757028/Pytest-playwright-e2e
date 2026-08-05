from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / "docs/implementation-ledger.yaml"
UX_STATUS_PATH = ROOT / "docs/ux-assurance-status.md"
PROJECT_STATUS_PATH = ROOT / "docs/implementation-status.md"
RUNTIME_DOC_PATH = ROOT / "docs/ux0-synthetic-user-shadow-runtime.md"
CLEANUP_PATH = ROOT / ".github/workflows/cleanup-implementation-branches.yml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def ux_module() -> dict[str, object]:
    ledger = load_yaml(LEDGER_PATH)
    return next(
        module
        for module in ledger["modules"]
        if module["module_id"] == "ux0-synthetic-user-shadow-runner"
    )


def test_ux_status_truthfully_records_verified_merge_pending_runtime() -> None:
    ux_status = UX_STATUS_PATH.read_text(encoding="utf-8")
    project_status = PROJECT_STATUS_PATH.read_text(encoding="utf-8")

    assert "Runtime：`VERIFIED_MERGE_PENDING`" in ux_status
    assert "Gate Mode：`SHADOW_NONBLOCKING`" in ux_status
    assert "Playwright Shadow Runner：VERIFIED / MERGE_PENDING" in ux_status
    assert "Advisory PR Gate：DISABLED" in ux_status
    assert "Blocking Release Gate：DISABLED" in ux_status
    assert "Human UAT：`REQUIRED`" in ux_status

    assert "Synthetic User Runtime：VERIFIED / MERGE_PENDING" in project_status
    assert "UX Gate Mode：SHADOW / NONBLOCKING" in project_status
    assert "M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT" in project_status
    assert "M1 Memory Gate：0 / 1" in project_status
    assert "Stage Delivery：NOT_READY" in project_status


def test_ux_ledger_binds_focused_full_and_replay_evidence() -> None:
    module = ux_module()
    evidence = module["test_evidence"]
    notes = "\n".join(module["notes"])

    assert module["status"] == "VERIFIED"
    assert module["branch"] == "agent/ux0-synthetic-user-shadow-runner"
    assert module["pull_request"] == 32
    assert module["commit"] == "c55448e99f850fdc1e4b7e3182072f6fe60bffdd"
    assert module["ci_run"] == 30991412463
    assert "9 focused Unit/Contract PASS" in evidence["unit_result"]
    assert "4 real TodoMVC Playwright journeys" in evidence["integration_result"]
    assert "14/14 checkpoints PASS" in evidence["integration_result"]
    assert "independent replay PASS" in evidence["integration_result"]
    assert "github-actions-artifact:8924285005" in evidence["asset_paths"]
    assert "Full Repository CI Run #125 / 30991412405 SUCCESS" in notes
    assert "sha256:349f51fa11cca5c5f83bee863c69b289" in notes
    assert "sha256:1dda03adfcc3a264240b20a883daf2a230e3ce6dcd00c43dccfb84da40b885c5" in notes
    assert "sha256:702fdce96eedbb8b81566dda08768d33434346a7edf88653594587f676c92fa4" in notes


def test_runtime_document_preserves_shadow_and_human_uat_boundaries() -> None:
    runtime_doc = RUNTIME_DOC_PATH.read_text(encoding="utf-8")

    assert "UX0-SYNTHETIC-USER-SHADOW@1.0.0" in runtime_doc
    assert "test-workflow ux validate" in runtime_doc
    assert "test-workflow ux run" in runtime_doc
    assert "test-workflow ux replay" in runtime_doc
    assert "NONBLOCKING_SHADOW" in runtime_doc
    assert "Human UAT：`REQUIRED`" in runtime_doc
    assert "Real Playwright Journeys：4 / 4 PASS" in runtime_doc
    assert "Independent Replay：PASS" in runtime_doc
    assert "Advisory 或 Blocking Gate" in runtime_doc


def test_cleanup_and_status_do_not_enable_advisory_or_blocking() -> None:
    cleanup = CLEANUP_PATH.read_text(encoding="utf-8")
    combined_status = (
        UX_STATUS_PATH.read_text(encoding="utf-8")
        + PROJECT_STATUS_PATH.read_text(encoding="utf-8")
    )

    assert '"agent/ux0-synthetic-user-shadow-runner"' in cleanup
    assert "ADVISORY_ENABLED" not in combined_status
    assert "BLOCKING_ENABLED" not in combined_status
    assert "Release Effect 固定为 `NONBLOCKING_SHADOW`" in combined_status
