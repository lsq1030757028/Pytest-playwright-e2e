from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .config import TestSettings


def build_pytest_command(
    settings: TestSettings,
    marker: str,
    browser: str,
    junit_path: Path,
) -> list[str]:
    return [
        "pytest",
        "tests",
        "-m",
        marker,
        "--browser",
        browser,
        "--tracing",
        "retain-on-failure",
        "--screenshot",
        "only-on-failure",
        "--video",
        "retain-on-failure",
        "--output",
        str(settings.artifacts_dir),
        "--junitxml",
        str(junit_path),
    ]


def run_tests(settings: TestSettings, marker: str, browser: str) -> int:
    if browser not in settings.browsers:
        raise ValueError(f"browser {browser!r} is not enabled in configuration")

    artifacts_dir = Path(settings.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    junit_path = artifacts_dir / "junit.xml"
    command = build_pytest_command(settings, marker, browser, junit_path)

    environment = os.environ.copy()
    environment["TEST_WORKFLOW_BASE_URL"] = str(settings.base_url)
    environment["TEST_WORKFLOW_ENVIRONMENT"] = settings.environment
    environment["TEST_WORKFLOW_ALLOW_WRITE"] = str(settings.allow_write).lower()

    completed = subprocess.run(command, env=environment, check=False)
    return completed.returncode
