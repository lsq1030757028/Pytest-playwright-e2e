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


def test_ux_status_truthfully_records_closed_runtime_and_ux1_spec() -> None:
    ux_status = UX_STATUS_PATH.read_text(encoding="utf-8")
    project_status = PROJECT_STATUS_PATH.read_text(encoding="utf-8")

    assert "UX0 Playwright Shadow Runtime：MERGED / CLOSED" in ux_status
    assert "TodoMVC UX Mutation Proof：SPEC_DRAFT" in ux_status
    assert "UX Mutation Proof Runner：NOT_IMPLEMENTED" in ux_status
    assert "Gate Mode：`SHADOW_NONBLOCKING`" in ux_status
    assert "Advisory PR Gate：DISABLED" in ux_status
    assert "Blocking Release Gate：DISABLED" in ux_status
    assert "Human UAT：`REQUIRED`" in ux_status

    assert "UX0 Synthetic User Runtime：MERGED / CLOSED" in project_status
    assert "TodoMVC UX Mutation Proof：SPEC_DRAFT" in project_status
    assert "UX Mutation Proof Runner：NOT_IMPLEMENTED" in project_status
    assert "UX Gate Mode：SHADOW / NONBLOCKING" in project_status
    assert "M1A Memory Contracts & Namespaces：SPEC_DRAFT_NEXT" in project_status
    assert "M1 Memory Gate：0 / 1" in project_status
    assert "Stage Delivery：NOT_READY" in project_status


def test_ux_ledger_binds_final_main_release_and_replay_evidence() -> None:
    module = ux_module()
    evidence = module["test_evidence"]
    notes = "\n".join(module["notes"])

    assert module["status"] == "MERGED"
    assert module["branch"] == "main"
    assert module["pull_request"] == 32
    assert module["commit"] == "f687fd9c30873c4a81d9ffb57b20459fdcebe4ee"
    assert module["ci_run"] == 30993021825
    assert "17 focused Unit/Contract/Delivery/Approval PASS" in evidence["unit_result"]
    assert "4 real TodoMVC Playwright journeys" in evidence["integration_result"]
    assert "14/14 checkpoints PASS" in evidence["integration_result"]
    assert "independent replay PASS" in evidence["integration_result"]
    assert "github-actions-artifact:8924951167" in evidence["asset_paths"]
    assert "python-distribution-artifact:8924921509" in evidence["asset_paths"]
    assert "docker-build-record:8924949424" in evidence["asset_paths"]
    assert "Main Quality Run #135 / 30993021825 SUCCESS" in notes
    assert "Release Run #12 / 30993022051 SUCCESS" in notes
    assert "Cleanup Run #10 / 30993021598 SUCCESS" in notes
    assert "sha256:afd95dfea4ba738494bc24e2c9b2c224" in notes
    assert "sha256:1dda03adfcc3a264240b20a883daf2a230e3ce6dcd00c43dccfb84da40b885c5" in notes
    assert "sha256:702fdce96eedbb8b81566dda08768d33434346a7edf88653594587f676c92fa4" in notes
    assert "implementation branch deleted" in notes


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
    assert '"docs/ux0-shadow-final-ledger"' in cleanup
    assert '"spec/ux1-todomvc-ux-mutation-proof"' in cleanup
    assert "ADVISORY_ENABLED" not in combined_status
    assert "BLOCKING_ENABLED" not in combined_status
    assert "Release Effect 固定为 `NONBLOCKING_SHADOW`" in combined_status
