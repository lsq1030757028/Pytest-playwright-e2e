from __future__ import annotations

import sys
from pathlib import Path

import httpx

from .config import TestSettings
from .models import CheckResult, PreflightResult, QualityGate


def run_preflight(settings: TestSettings) -> PreflightResult:
    checks: list[CheckResult] = []

    checks.append(
        CheckResult(
            name="python_version",
            passed=sys.version_info >= (3, 11),
            detail=f"Python {sys.version_info.major}.{sys.version_info.minor}",
        )
    )

    artifacts_dir = Path(settings.artifacts_dir)
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        probe = artifacts_dir / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(CheckResult(name="artifacts_dir", passed=True, detail=str(artifacts_dir)))
    except OSError as exc:
        checks.append(CheckResult(name="artifacts_dir", passed=False, detail=str(exc)))

    is_production = settings.environment.lower() in {"prod", "production", "online"}
    write_policy_ok = not (is_production and settings.allow_write)
    checks.append(
        CheckResult(
            name="write_policy",
            passed=write_policy_ok,
            detail=(
                "production write operations are disabled"
                if write_policy_ok
                else "production write operations require explicit external approval"
            ),
        )
    )

    try:
        response = httpx.get(settings.health_url, timeout=settings.request_timeout_seconds)
        healthy = response.is_success
        detail = f"HTTP {response.status_code} {settings.health_url}"
    except httpx.HTTPError as exc:
        healthy = False
        detail = f"{settings.health_url}: {exc}"
    checks.append(CheckResult(name="health_endpoint", passed=healthy, detail=detail))

    status = QualityGate.PASS if all(check.passed for check in checks) else QualityGate.BLOCKED
    return PreflightResult(environment=settings.environment, status=status, checks=checks)
