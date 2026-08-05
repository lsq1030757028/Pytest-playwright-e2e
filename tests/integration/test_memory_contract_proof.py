import json
from pathlib import Path

from test_workflow.memory_contracts.proof import (
    replay_contract_proof,
    run_contract_proof,
)


def test_contract_proof_and_independent_replay(tmp_path: Path) -> None:
    report = run_contract_proof(tmp_path, code_sha="a" * 40)
    replay = replay_contract_proof(tmp_path)

    assert report.verdict == "PASS"
    assert report.metrics.total == 15
    assert report.metrics.passed == 15
    assert report.metrics.critical_false_green == 0
    assert report.metrics.unauthorized_namespace_actions == 0
    assert report.metrics.unauthorized_promotion_actions == 0
    assert replay.passed is True
    assert replay.replay_semantic_digest == report.semantic_digest
    assert (tmp_path / "artifact-manifest.json").is_file()
    assert (tmp_path / "replay-result.json").is_file()


def test_contract_proof_replay_rejects_tampered_report(tmp_path: Path) -> None:
    run_contract_proof(tmp_path, code_sha="b" * 40)
    report_path = tmp_path / "contract-report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["metrics"]["passed"] = 999
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    replay = replay_contract_proof(tmp_path)

    assert replay.passed is False
    assert "digest mismatch" in (replay.error or "")
