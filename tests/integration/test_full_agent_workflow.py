from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_workflow.harness import (
    AssuranceLevel,
    AssuranceRouter,
    ChangeSignals,
    SourceRevisionRegistry,
    SourceRole,
    SourceStatus,
)
from test_workflow.harness.diagnosis import (
    EvidenceItem,
    EvidenceType,
    FailureCategory,
    FailureEvidence,
    RuleFirstDiagnoser,
    evidence_hash,
)
from test_workflow.harness.generation import (
    AITestSpecCompiler,
    CandidateProofGate,
    FreeTimeTestGenerator,
    SafePythonTestValidator,
)
from test_workflow.harness.intelligence import (
    BusinessPriority,
    HiddenUnderstandingEvaluator,
    IncrementalBusinessCompiler,
    MockModelProvider,
    ReleaseAction,
    RiskPromotionEngine,
)
from test_workflow.harness.regression import (
    BenchmarkCase,
    BenchmarkEvaluator,
    ImpactMapping,
    RegressionGraph,
    RegressionSelector,
    TestAssetRecord,
    TestLayer,
)
from test_workflow.harness.verdict import VerdictBuilder, VerdictStatus

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = REPO_ROOT / "tests/assets/harness/full-workflow"


def regression_asset(
    test_id: str,
    priority: BusinessPriority,
    tags: frozenset[str],
    duration: float,
) -> TestAssetRecord:
    return TestAssetRecord(
        test_id=test_id,
        requirement_refs=("REQ-FREE@v1",),
        source_refs=("examples/demo_app/main.py",),
        domain_tags=tags,
        layer=TestLayer.UNIT,
        priority=priority,
        duration_seconds=duration,
        baseline_passed=True,
        mutation_killed=True,
        stability_runs=3,
        stability_passed=3,
    )


@pytest.mark.harness_integration
def test_full_agent_workflow_produces_independently_proven_verdict(tmp_path: Path) -> None:
    sources = SourceRevisionRegistry()
    sources.register_source(
        source_id="source-free-time",
        source_type="requirement",
        role=SourceRole.PRODUCT_OWNER,
        content="Two free minutes include an exact 120 second close.",
        status=SourceStatus.APPROVED,
    )
    revision = sources.add_revision(
        revision_id="REQ-FREE@v1",
        requirement_id="REQ-FREE",
        version=1,
        content="Two free minutes include an exact 120 second close.",
        source_id="source-free-time",
        approved=True,
    )
    assurance = AssuranceRouter().route(ChangeSignals(money=True))
    assert assurance.level == AssuranceLevel.L3

    business_response = json.loads(
        (ASSET_ROOT / "business-response.json").read_text(encoding="utf-8")
    )
    spec_response = json.loads(
        (ASSET_ROOT / "test-spec.json").read_text(encoding="utf-8")
    )
    understanding = IncrementalBusinessCompiler(
        MockModelProvider({"business-understanding": business_response})
    ).compile(
        requirement_revision_id=revision.revision_id,
        assurance_level=assurance.level,
        requirement_text="Two free minutes include an exact 120 second close.",
        scope=("billing.free-time",),
    )
    understanding_evaluation = HiddenUnderstandingEvaluator().evaluate(
        understanding,
        required_invariant_ids=frozenset({"INV-BILLING-BOUNDARY"}),
        required_p0_scenarios=frozenset({"LOSS-BILLING-BOUNDARY"}),
    )
    compiled = AITestSpecCompiler(
        MockModelProvider({"test-spec": spec_response}),
        provider_name="mock-golden",
    ).compile(understanding)
    candidate = FreeTimeTestGenerator().generate(compiled)
    code_validation = SafePythonTestValidator().validate(candidate)
    generated_test = tmp_path / "test_generated_free_time.py"
    generated_test.write_text(candidate.code, encoding="utf-8")
    proof = CandidateProofGate(REPO_ROOT).verify(
        test_path=generated_test,
        mutation_path=REPO_ROOT / "examples/demo_app/main.py",
        find="close_seconds <= free_seconds",
        replace="close_seconds < free_seconds",
    )

    loss_decision = RiskPromotionEngine().decide(
        understanding.loss_scenarios[0],
        reproduced=True,
    )
    summary = "independent state probe confirms the mutated boundary violates the oracle"
    diagnosis = RuleFirstDiagnoser().diagnose(
        FailureEvidence(
            run_id="negative-control",
            items=(
                EvidenceItem(
                    evidence_id="state-negative-control",
                    evidence_type=EvidenceType.STATE_PROBE,
                    source="generated-test",
                    summary=summary,
                    content_hash=evidence_hash(summary),
                    attributes={"oracle_mismatch": True},
                ),
            ),
        )
    )

    graph = RegressionGraph(
        tests=(
            regression_asset(
                "generated-boundary",
                BusinessPriority.P0,
                frozenset({"billing", "free-time"}),
                3,
            ),
            regression_asset(
                "billing-smoke",
                BusinessPriority.P2,
                frozenset({"smoke"}),
                2,
            ),
            regression_asset(
                "unrelated-account",
                BusinessPriority.P2,
                frozenset({"account"}),
                20,
            ),
        ),
        mappings=(
            ImpactMapping(
                change_ref="billing.free-time",
                test_id="generated-boundary",
            ),
        ),
    )
    selection = RegressionSelector().select(
        graph,
        changed_refs=frozenset({"billing.free-time"}),
        assurance_level=assurance.level,
    )
    benchmark = BenchmarkEvaluator().evaluate(
        (
            BenchmarkCase(
                case_id="free-time-boundary",
                expected_critical_tests=frozenset({"generated-boundary"}),
                expected_all_tests=frozenset({"generated-boundary", "billing-smoke"}),
                selected_tests=frozenset(selection.selected_test_ids),
                defect_present=True,
                verdict_passed=False,
                execution_seconds=selection.estimated_seconds,
                full_suite_seconds=selection.full_suite_seconds,
            ),
        )
    )
    verdict = VerdictBuilder().build(
        assurance=assurance,
        understanding=understanding_evaluation,
        compiled_spec=compiled,
        code_validation=code_validation,
        proof=proof,
        negative_control_diagnosis=diagnosis,
        regression=selection,
        benchmark=benchmark,
    )

    assert understanding_evaluation.passed is True
    assert loss_decision.release_action == ReleaseAction.BLOCK
    assert diagnosis.category == FailureCategory.PRODUCT_DEFECT
    assert proof.passed is True
    assert benchmark.passed is True
    assert verdict.status == VerdictStatus.PASS
    assert verdict.baseline == "PASS"
    assert verdict.negative_control == "FAIL"
    assert verdict.restored == "PASS"
    assert verdict.false_green_count == 0
    assert verdict.blockers == ()
