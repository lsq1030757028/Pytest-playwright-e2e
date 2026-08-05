from __future__ import annotations

from pathlib import Path

import pytest

from test_workflow.harness import CapabilityDescriptor, CapabilityRequest, CapabilityResult

ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "harness" / "3.0a"


@pytest.mark.harness_integration
def test_golden_contract_assets_form_one_traceable_execution_chain() -> None:
    descriptor = CapabilityDescriptor.model_validate_json(
        (ASSET_ROOT / "descriptor.json").read_text(encoding="utf-8")
    )
    request = CapabilityRequest.model_validate_json(
        (ASSET_ROOT / "request.json").read_text(encoding="utf-8")
    )
    result = CapabilityResult.model_validate_json(
        (ASSET_ROOT / "result.json").read_text(encoding="utf-8")
    )

    assert request.capability == descriptor.ref
    assert request.input_artifacts[0].artifact_type == descriptor.input_types[0].name
    assert result.artifacts[0].artifact_type == descriptor.output_types[0].name
    assert result.request_id == request.request_id
    assert result.events[0].campaign_id == request.campaign_id
    assert result.events[0].correlation_id == request.correlation_id
    assert CapabilityResult.model_validate_json(result.model_dump_json()) == result
