from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from test_workflow.bundle import (
    create_replay_manifest,
    replay_bundle,
    validate_replay_bundle,
)
from test_workflow.mocking import validate_mock_configuration


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_BUNDLE = REPO_ROOT / "experiments" / "todomvc-golden-loop"


def copy_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "bundle"
    shutil.copytree(EXAMPLE_BUNDLE, target, ignore=shutil.ignore_patterns(".runtime", "evidence"))
    return target


def test_example_mock_plan_respects_truth_boundary_and_contract() -> None:
    report = validate_mock_configuration(EXAMPLE_BUNDLE)
    assert report.valid, report.model_dump_json(indent=2)


def test_mock_plan_rejects_control_of_business_logic(tmp_path: Path) -> None:
    bundle = copy_bundle(tmp_path)
    plan_path = bundle / "environment" / "mock-plan.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    plan["dependencies"].append(
        {
            "dependency": "todo.create",
            "decision": "control",
            "reason": "invalid attempt to bypass business logic",
            "risk": "critical",
        }
    )
    plan_path.write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    report = validate_mock_configuration(bundle)

    assert report.valid is False
    assert any(
        error.code == "truth_boundary.mocked_real_component" for error in report.errors
    )


def test_mock_plan_detects_contract_drift(tmp_path: Path) -> None:
    bundle = copy_bundle(tmp_path)
    contract = bundle / "environment" / "contracts" / "telemetry-response.schema.json"
    contract.write_text(contract.read_text() + "\n", encoding="utf-8")

    report = validate_mock_configuration(bundle)

    assert report.valid is False
    assert any(error.code == "contract.hash_mismatch" for error in report.errors)


def test_manifest_detects_tampered_seed(tmp_path: Path) -> None:
    bundle = copy_bundle(tmp_path)
    create_replay_manifest(
        bundle,
        command=["python", "-m", "pytest", "generated", "-q"],
        run_id="test-tamper",
    )
    seed = bundle / "environment" / "data-seed.yaml"
    seed.write_text(seed.read_text() + "\n# tampered\n", encoding="utf-8")

    report = validate_replay_bundle(bundle)

    assert report.valid is False
    assert any(error.code == "bundle.artifact_hash_mismatch" for error in report.errors)


def test_independent_replay_executes_generated_proof(tmp_path: Path) -> None:
    bundle = copy_bundle(tmp_path)
    create_replay_manifest(
        bundle,
        command=["python", "-m", "pytest", "generated", "-q"],
        run_id="test-replay",
    )

    return_code = replay_bundle(bundle)

    assert return_code == 0
    assert (bundle / "evidence" / "replay-result.json").is_file()
    assert "2 passed" in (bundle / "evidence" / "stdout.log").read_text()
