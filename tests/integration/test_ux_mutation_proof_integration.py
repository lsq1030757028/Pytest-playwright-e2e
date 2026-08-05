from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_workflow.serialization import load_model
from test_workflow.ux_mutation import (
    MutationOutcome,
    ProofCampaignVerdict,
    UXMutationProofRunner,
)
from test_workflow.ux_mutation.models import UXMutationArtifactManifest

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "benchmarks/ux/ux1/campaign.yaml"


@pytest.mark.ux_integration
def test_real_todomvc_five_mutation_proof_and_independent_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("RUN_UX_MUTATION_INTEGRATION") != "1":
        pytest.skip("RUN_UX_MUTATION_INTEGRATION=1 is required")
    monkeypatch.setenv("UX_CODE_SHA", os.getenv("UX_CODE_SHA", "b" * 40))

    configured_output = os.getenv("UX_MUTATION_EVIDENCE_DIR")
    configured_workspace = os.getenv("UX_MUTATION_WORKSPACE")
    output = (
        Path(configured_output).resolve()
        if configured_output
        else tmp_path / "ux-mutation-output"
    )
    workspace = (
        Path(configured_workspace).resolve()
        if configured_workspace
        else tmp_path / "ux-mutation-workspace"
    )
    replay_workspace = workspace.parent / "ux-mutation-replay-workspace"
    runner = UXMutationProofRunner()

    report = runner.run(
        CAMPAIGN,
        workspace=workspace,
        output_dir=output,
        verify_replay=False,
    )

    diagnostic = report.model_dump_json(indent=2)
    assert report.verdict == ProofCampaignVerdict.PASS, diagnostic
    assert report.mode == "SHADOW"
    assert report.release_effect == "NONBLOCKING_SHADOW"
    assert report.human_uat_required is True
    assert report.metrics.total_mutations == 5
    assert report.metrics.killed_mutations == 5
    assert report.metrics.critical_mutation_kill_rate_percent == 100
    assert report.metrics.baseline_false_positive_count == 0
    assert report.metrics.critical_false_green_count == 0
    assert report.metrics.exact_restore_percent == 100
    assert report.metrics.hidden_metadata_leakage_count == 0
    assert report.metrics.undeclared_changed_files_count == 0
    assert report.metrics.ai_only_kill_count == 0
    assert all(
        result.outcome == MutationOutcome.KILLED
        for result in report.mutation_results
    ), diagnostic
    assert all(result.actor_input_consistent for result in report.mutation_results)
    assert all(result.exact_restore for result in report.mutation_results)
    assert all(result.baseline is not None for result in report.mutation_results)
    assert all(result.mutated is not None for result in report.mutation_results)
    assert all(result.restored is not None for result in report.mutation_results)

    for result in report.mutation_results:
        mutation_dir = output / result.evidence_path
        for phase in ("baseline", "mutated", "restored"):
            phase_dir = mutation_dir / phase
            assert (phase_dir / "report.json").is_file()
            assert (phase_dir / "report.md").is_file()
            assert (phase_dir / "artifact-manifest.json").is_file()
            assert any(phase_dir.glob("evidence/*/trace.zip"))
            assert any(phase_dir.glob("evidence/*/final.png"))
            assert any(phase_dir.glob("evidence/*/semantic.json"))

    manifest = load_model(
        output / "artifact-manifest.json",
        UXMutationArtifactManifest,
    )
    assert "report.json" in manifest.files
    assert "input/plan.json" in manifest.files
    assert any(path.endswith("trace.zip") for path in manifest.files)
    assert any(path.endswith("semantic.json") for path in manifest.files)

    replayed = runner.replay(output, workspace=replay_workspace)
    assert replayed.verdict == ProofCampaignVerdict.PASS
    assert replayed.semantic_digest == report.semantic_digest
    assert replayed.metrics.replay_percent == 100

    report_markdown = output / "report.md"
    report_markdown.write_text(
        report_markdown.read_text(encoding="utf-8") + "tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        runner.replay(
            output,
            workspace=workspace.parent / "tamper-replay-workspace",
        )
