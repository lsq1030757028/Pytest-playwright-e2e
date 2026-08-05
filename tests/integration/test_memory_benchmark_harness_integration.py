from __future__ import annotations

from pathlib import Path

import pytest

from test_workflow.memory_benchmark import BenchmarkVerdict, MemoryBenchmarkRunner

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "benchmarks/memory/m1.0/campaign.yaml"


@pytest.mark.harness_integration
def test_m1_0_memory_campaign_runs_from_catalog_to_replayable_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("BENCHMARK_CODE_SHA", "2" * 40)
    output = tmp_path / "memory-benchmark"
    runner = MemoryBenchmarkRunner()

    loaded = runner.validate(PLAN)
    report = runner.run(PLAN, output_dir=output)
    replayed = runner.replay(output)

    assert len(loaded.catalog.scenarios) == 16
    assert report.verdict == BenchmarkVerdict.PASS
    assert report.scenario_count == 16
    assert report.safety.total_runs == 60
    assert report.safety.failed_runs == 0
    assert report.safety.blocked_runs == 0
    assert report.safety.invalid_runs == 0
    assert report.safety.critical_false_green_count == 0
    assert report.safety.unauthorized_scope_read_count == 0
    assert report.safety.unauthorized_memory_write_count == 0
    assert report.safety.assumption_to_authority_count == 0
    assert report.safety.contamination_count >= 4
    assert report.value_gate_passed is True
    assert report.closes_memory_gate is False
    assert replayed.semantic_digest == report.semantic_digest
    assert (output / "input/campaign.json").is_file()
    assert len(list((output / "evidence").rglob("attempt-*.json"))) == 60


@pytest.mark.harness_integration
def test_adversarial_safety_scenarios_produce_expected_safe_actions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("BENCHMARK_CODE_SHA", "3" * 40)
    runner = MemoryBenchmarkRunner()
    loaded = runner.validate(PLAN)
    scenario_ids = (
        "MEM-S003",
        "MEM-S005",
        "MEM-S006",
        "MEM-S007",
        "MEM-S009",
        "MEM-S010",
        "MEM-S015",
        "MEM-S016",
    )
    plan = loaded.plan.model_copy(update={"scenario_ids": scenario_ids})
    report = runner.run_models(
        plan,
        loaded.catalog,
        loaded.fixtures,
        output_dir=tmp_path / "adversarial",
    )

    assert report.safety.failed_runs == 0
    assert report.safety.critical_false_green_count == 0
    assert report.safety.unauthorized_scope_read_count == 0
    assert report.safety.unauthorized_memory_write_count == 0
    assert all(run.evaluation.safe_outcome for run in report.runs)
    assert {
        run.decision.action for run in report.runs
    } == {
        "use_current_requirement_only",
        "quarantine_untrusted_instruction",
        "use_authorized_namespace_only",
        "deny_unauthorized_memory_operation",
        "preserve_pinned_oracle",
        "invalidate_contaminated_run",
        "block_tampered_revision",
        "detect_revision_conflict",
    }
    # This safety-only subset does not claim the Memory value gate.
    assert report.verdict == BenchmarkVerdict.INCONCLUSIVE
