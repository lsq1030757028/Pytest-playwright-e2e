from pathlib import Path

import httpx
import pytest

from test_workflow.config import TestSettings as WorkflowSettings
from test_workflow.models import QualityGate
from test_workflow.preflight import run_preflight


class HealthyResponse:
    is_success = True
    status_code = 200


def test_preflight_passes_for_healthy_non_production_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: HealthyResponse())
    settings = WorkflowSettings(
        environment="test",
        base_url="http://example.test",
        allow_write=True,
        artifacts_dir=tmp_path / "artifacts",
    )

    result = run_preflight(settings)

    assert result.status == QualityGate.PASS
    assert all(check.passed for check in result.checks)


def test_preflight_blocks_production_write_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: HealthyResponse())
    settings = WorkflowSettings(
        environment="production",
        base_url="https://example.test",
        allow_write=True,
        artifacts_dir=tmp_path / "artifacts",
    )

    result = run_preflight(settings)

    assert result.status == QualityGate.BLOCKED
    assert next(check for check in result.checks if check.name == "write_policy").passed is False
