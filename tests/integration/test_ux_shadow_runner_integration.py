from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_workflow.serialization import load_model
from test_workflow.ux import UXShadowRunner, UXVerdict
from test_workflow.ux.models import UXArtifactManifest

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "benchmarks/ux/ux0/campaign.yaml"


@pytest.mark.ux_integration
def test_real_todomvc_shadow_journeys_and_independent_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("RUN_UX_INTEGRATION") != "1":
        pytest.skip("RUN_UX_INTEGRATION=1 is required")
    code_sha = os.getenv("UX_CODE_SHA", "b" * 40)
    monkeypatch.setenv("UX_CODE_SHA", code_sha)
    runner = UXShadowRunner()
    configured_output = os.getenv("UX_EVIDENCE_DIR")
    output = Path(configured_output).resolve() if configured_output else tmp_path / "ux-output"
    workspace = output.parent / "workspace" if configured_output else tmp_path / "workspace"

    report = runner.run(
        CAMPAIGN,
        workspace=workspace,
        output_dir=output,
    )

    diagnostic = report.model_dump_json(indent=2)
    assert report.verdict == UXVerdict.PASS, diagnostic
    assert report.mode.value == "SHADOW"
    assert report.release_effect == "NONBLOCKING_SHADOW"
    assert report.human_uat_required is True
    assert len(report.runs) == 4
    assert all(run.evaluation.verdict == UXVerdict.PASS for run in report.runs), diagnostic
    assert all(run.metrics.task_completed for run in report.runs), diagnostic
    assert all(
        run.metrics.checkpoint_completed == run.metrics.checkpoint_total
        for run in report.runs
    ), diagnostic
    assert all(not finding.blocking for run in report.runs for finding in run.findings)

    run_map = {run.journey_ref.split("@", maxsplit=1)[0]: run for run in report.runs}
    assert run_map["novice-add-task"].metrics.feedback_observed is True
    assert run_map["returning-filter-persistence"].metrics.recovery_success is True
    assert run_map["keyboard-primary"].metrics.keyboard_completion is True
    assert run_map["keyboard-primary"].metrics.semantic_accessibility_failures == 0
    assert run_map["interrupted-resume"].metrics.recovery_success is True
    assert not any(run.metrics.unexpected_state_loss for run in report.runs)

    for run in report.runs:
        journey_dir = output / run.evidence_path
        assert (journey_dir / "trace.zip").is_file()
        assert (journey_dir / "final.png").is_file()
        assert (journey_dir / "semantic.json").is_file()
        assert run.events
        assert [event.sequence for event in run.events] == list(
            range(1, len(run.events) + 1)
        )
        assert all(event.before_state_hash for event in run.events)
        assert all(event.after_state_hash for event in run.events)
        assert all(event.evidence_refs for event in run.events)

    manifest = load_model(output / "artifact-manifest.json", UXArtifactManifest)
    assert "report.json" in manifest.files
    assert "input/campaign.json" in manifest.files
    assert any(path.endswith("trace.zip") for path in manifest.files)
    assert any(path.endswith("semantic.json") for path in manifest.files)

    replayed = runner.replay(output, workspace=output.parent / "replay-workspace")
    assert replayed.verdict == UXVerdict.PASS, replayed.model_dump_json(indent=2)
    assert replayed.semantic_digest == report.semantic_digest
