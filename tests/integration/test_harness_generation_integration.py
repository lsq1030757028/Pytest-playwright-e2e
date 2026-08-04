from __future__ import annotations

from pathlib import Path

import pytest

from test_workflow.harness import AssuranceLevel
from test_workflow.harness.generation import (
    AITestSpecCompiler,
    CandidateProofGate,
    FreeTimeTestGenerator,
    SafePythonTestValidator,
)
from test_workflow.harness.intelligence import (
    BusinessAsset,
    BusinessModel,
    BusinessPriority,
    MockModelProvider,
    UnderstandingArtifact,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.harness_integration
def test_generated_free_time_test_kills_boundary_mutation_and_restores_source(
    tmp_path: Path,
) -> None:
    understanding = UnderstandingArtifact(
        requirement_revision_id="REQ-FREE@v1",
        assurance_level=AssuranceLevel.L3,
        model=BusinessModel(
            model_id="free-time",
            scope=("billing.free-time",),
            assets=(
                BusinessAsset(
                    asset_id="billing-result",
                    name="Billing result",
                    asset_type="money",
                    priority=BusinessPriority.P0,
                ),
            ),
        ),
        loss_scenarios=(),
    )
    provider = MockModelProvider(
        {
            "test-spec": {
                "schema_version": "1.0",
                "id": "FREE-TIME-GENERATED-001",
                "title": "Free time exact boundary",
                "requirement_sources": [
                    {"id": "REQ-FREE", "source": "REQ-FREE@v1"}
                ],
                "facts": [
                    {
                        "id": "F-BOUNDARY",
                        "statement": "120 seconds is within two free minutes",
                        "source": "REQ-FREE",
                        "confidence": "confirmed",
                    }
                ],
                "assumptions": [],
                "risks": [
                    {
                        "id": "R-BOUNDARY",
                        "title": "exact boundary rejected",
                        "probability": "medium",
                        "impact": "high",
                        "test_required": True,
                    }
                ],
                "truth_boundary": {
                    "must_be_real": ["billing.free-time"],
                    "may_be_mocked": ["system.clock"],
                },
                "cases": [
                    {
                        "id": "CASE-BOUNDARY",
                        "title": "two minutes accepts 120 seconds",
                        "risk": "critical",
                        "preconditions": [],
                        "actions": [
                            {
                                "name": "calculate_free_time",
                                "params": {
                                    "free_minutes": 2,
                                    "close_seconds": 120,
                                },
                            }
                        ],
                        "oracles": [
                            {
                                "id": "O-BOUNDARY",
                                "source": "requirement",
                                "expression": "free_time_applied == true",
                                "expected": True,
                                "basis_ref": "F-BOUNDARY",
                                "confidence": "confirmed",
                            }
                        ],
                        "tags": ["critical", "boundary"],
                    }
                ],
                "regression_keys": ["billing", "free-time"],
            }
        }
    )
    compiled = AITestSpecCompiler(provider, provider_name="mock").compile(understanding)
    candidate = FreeTimeTestGenerator().generate(compiled)
    validation = SafePythonTestValidator().validate(candidate)
    test_path = tmp_path / "test_generated_free_time.py"
    test_path.write_text(candidate.code, encoding="utf-8")

    report = CandidateProofGate(REPO_ROOT).verify(
        test_path=test_path,
        mutation_path=REPO_ROOT / "examples/demo_app/main.py",
        find="close_seconds <= free_seconds",
        replace="close_seconds < free_seconds",
    )

    assert validation.valid is True
    assert report.baseline.return_code == 0
    assert report.mutation.return_code != 0
    assert report.restored.return_code == 0
    assert report.mutation_killed is True
    assert report.restored_hash_matches is True
    assert report.passed is True
