from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from test_workflow.harness import AssuranceLevel
from test_workflow.harness.generation import (
    AITestSpecCompiler,
    CandidateProofGate,
    CandidateTestCode,
    FreeTimeTestGenerator,
    SafePythonTestValidator,
    text_hash,
)
from test_workflow.harness.intelligence import (
    BusinessAsset,
    BusinessModel,
    BusinessPriority,
    MockModelProvider,
    UnderstandingArtifact,
)


def understanding() -> UnderstandingArtifact:
    return UnderstandingArtifact(
        requirement_revision_id="REQ-FREE@v1",
        assurance_level=AssuranceLevel.L2,
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


def spec_payload() -> dict:
    return {
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
                        "params": {"free_minutes": 2, "close_seconds": 120},
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


def compiled():
    provider = MockModelProvider({"test-spec": spec_payload()})
    return AITestSpecCompiler(provider, provider_name="mock").compile(understanding())


def test_ai_compiler_binds_requirement_and_understanding_hash() -> None:
    result = compiled()
    assert result.requirement_revision_id == "REQ-FREE@v1"
    assert result.provider == "mock"
    assert result.spec.id == "FREE-TIME-GENERATED-001"
    assert result.understanding_hash.startswith("sha256:")


def test_ai_compiler_uses_existing_testspec_oracle_validation() -> None:
    payload = spec_payload()
    payload["cases"][0]["oracles"][0]["basis_ref"] = "MISSING"
    with pytest.raises(ValidationError, match="unknown basis"):
        AITestSpecCompiler(MockModelProvider({"test-spec": payload})).compile(
            understanding()
        )


def test_generator_emits_readable_traceable_test() -> None:
    candidate = FreeTimeTestGenerator().generate(compiled())
    assert "Requirement: REQ-FREE@v1" in candidate.code
    assert "Oracles: O-BOUNDARY" in candidate.code
    assert "calculate_free_time(2, 120)" in candidate.code
    assert candidate.code_hash == text_hash(candidate.code)


def test_candidate_code_rejects_hash_mismatch() -> None:
    with pytest.raises(ValidationError, match="hash mismatch"):
        CandidateTestCode(
            test_id="bad",
            requirement_revision_id="REQ@v1",
            spec_id="SPEC",
            oracle_ids=("O-1",),
            code="def test_x(): assert True",
            code_hash="sha256:" + "a" * 64,
        )


def test_safe_validator_accepts_generated_code() -> None:
    result = SafePythonTestValidator().validate(
        FreeTimeTestGenerator().generate(compiled())
    )
    assert result.valid is True
    assert result.assertion_count == 3
    assert result.test_function_count == 1


def test_safe_validator_rejects_sleep_network_and_constant_assertion() -> None:
    code = "import requests\nimport time\n\ndef test_bad():\n    time.sleep(1)\n    assert True\n"
    candidate = CandidateTestCode(
        test_id="bad",
        requirement_revision_id="REQ@v1",
        spec_id="SPEC",
        oracle_ids=("O-1",),
        code=code,
        code_hash=text_hash(code),
    )
    result = SafePythonTestValidator().validate(candidate)
    assert result.valid is False
    assert any("forbidden import" in item for item in result.errors)
    assert any("forbidden call" in item for item in result.errors)
    assert "constant assertion is not allowed" in result.errors


def test_proof_gate_rejects_ambiguous_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    test = tmp_path / "test_source.py"
    source.write_text("x = 1\nx = 1\n", encoding="utf-8")
    test.write_text("def test_x(): assert True\n", encoding="utf-8")
    gate = CandidateProofGate(tmp_path)
    with pytest.raises(ValueError, match="occur once"):
        gate.verify(test_path=test, mutation_path=source, find="x = 1", replace="x = 2")
