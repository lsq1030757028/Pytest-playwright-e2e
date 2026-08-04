from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from test_workflow.harness.ledger import load_implementation_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.harness_integration
def test_implementation_ledger_and_release_assets_are_deployable() -> None:
    ledger = load_implementation_ledger(REPO_ROOT / "docs/implementation-ledger.yaml")
    release_text = (REPO_ROOT / ".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    workflow = yaml.safe_load(release_text)

    assert ledger.project == "AI Test Harness"
    assert len(ledger.modules) >= 15
    assert "docker/build-push-action@v6" in release_text
    assert "ghcr.io/${{ github.repository }}" in release_text
    assert "uv build" in release_text
    assert workflow["jobs"]["build-and-publish"]
    assert 'USER pwuser' in dockerfile
    assert 'ENTRYPOINT ["test-workflow"]' in dockerfile
    assert "COPY targets ./targets" in dockerfile
    assert "COPY proofs ./proofs" in dockerfile
