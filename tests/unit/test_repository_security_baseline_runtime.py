from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CODEQL_PATH = ROOT / ".github/workflows/security-codeql.yml"
SECRETS_PATH = ROOT / ".github/workflows/security-secrets.yml"
DEPENDABOT_PATH = ROOT / ".github/dependabot.yml"
SECURITY_PATH = ROOT / "SECURITY.md"
INSTALLER_PATH = ROOT / "scripts/security/install_gitleaks.sh"
RUNNER_PATH = ROOT / "scripts/security/run_gitleaks.sh"
PROOF_PATH = ROOT / "scripts/security/prove_gitleaks_history.sh"
SUMMARY_PATH = ROOT / "scripts/security/summarize_gitleaks.py"
SELECTION_PATH = ROOT / "docs/security/secret-scanner-selection.md"
SHA_REF = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def action_refs(workflow: dict[str, object]) -> list[str]:
    refs: list[str] = []
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    for job in jobs.values():
        assert isinstance(job, dict)
        steps = job.get("steps", [])
        assert isinstance(steps, list)
        for step in steps:
            assert isinstance(step, dict)
            reference = step.get("uses")
            if reference is not None:
                refs.append(str(reference))
    return refs


def test_codeql_is_python_scoped_pinned_and_least_privilege() -> None:
    workflow = load_yaml(CODEQL_PATH)
    raw = CODEQL_PATH.read_text(encoding="utf-8")

    assert set(workflow["on"]) == {"pull_request", "push", "workflow_dispatch"}
    assert "pull_request_target" not in raw
    assert workflow["permissions"] == {
        "actions": "read",
        "contents": "read",
        "packages": "read",
        "security-events": "write",
    }
    refs = action_refs(workflow)
    assert refs
    assert all(SHA_REF.fullmatch(reference) for reference in refs)
    assert raw.count("c4dd10e44af883a891fe31ced449bcb4a6728b9b") == 2
    assert "languages: python" in raw
    assert "queries: security-extended" in raw
    assert "persist-credentials: false" in raw
    assert "${{ secrets." not in raw


def test_secret_workflow_scans_complete_history_without_privilege_or_artifacts() -> None:
    workflow = load_yaml(SECRETS_PATH)
    raw = SECRETS_PATH.read_text(encoding="utf-8")

    assert set(workflow["on"]) == {"pull_request", "push", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert all(SHA_REF.fullmatch(reference) for reference in action_refs(workflow))
    assert "fetch-depth: 0" in raw
    assert "persist-credentials: false" in raw
    assert "rev-parse --is-shallow-repository" in raw
    assert "prove_gitleaks_history.sh" in raw
    assert "run_gitleaks.sh" in raw
    assert "upload-artifact" not in raw
    assert "pull_request_target" not in raw
    assert "${{ secrets." not in raw


def test_gitleaks_install_and_scan_are_pinned_redacted_and_fail_closed() -> None:
    installer = INSTALLER_PATH.read_text(encoding="utf-8")
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    summary = SUMMARY_PATH.read_text(encoding="utf-8")

    assert "8.30.1" in installer
    assert "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb" in installer
    assert "sha256sum --check --status" in installer
    assert "curl" in installer
    assert "| sh" not in installer
    assert '--log-opts="--all"' in runner
    assert "--redact=100" in runner
    assert "--exit-code=42" in runner
    assert "summarize_gitleaks.py" in runner
    assert "cat \"$report\"" not in runner
    assert 'finding.get("Secret")' not in summary
    assert 'finding.get("Match")' not in summary


def test_synthetic_proof_requires_earlier_commit_detection_and_zero_canary_output() -> None:
    proof = PROOF_PATH.read_text(encoding="utf-8")

    assert "add synthetic historical canary" in proof
    assert "remove synthetic historical canary" in proof
    assert "origin_commit" in proof
    assert 'grep -Fq "$origin_commit" "$report"' in proof
    assert 'grep -Fq "$canary"' in proof
    assert "test \"$status\" -eq 42" in proof
    assert "github_pat_" in proof
    assert "echo \"$canary\"" not in proof


def test_dependabot_covers_python_and_actions_with_bounded_weekly_updates() -> None:
    config = load_yaml(DEPENDABOT_PATH)
    updates = config["updates"]
    assert isinstance(updates, list)
    by_ecosystem = {item["package-ecosystem"]: item for item in updates}

    assert set(by_ecosystem) == {"pip", "github-actions"}
    for update in by_ecosystem.values():
        assert update["directory"] == "/"
        assert update["schedule"]["interval"] == "weekly"
        assert update["schedule"]["timezone"] == "Asia/Shanghai"
        assert 1 <= update["open-pull-requests-limit"] <= 5


def test_security_policy_has_private_reporting_and_safe_research_boundaries() -> None:
    policy = SECURITY_PATH.read_text(encoding="utf-8")

    assert "Report a vulnerability" in policy
    assert "targets, not guaranteed resolution deadlines" in policy
    assert "coordinated disclosure" in policy.lower()
    assert "real customer data" in policy
    assert "live credentials" in policy
    assert "revoked or rotated" in policy
    assert "Never paste the credential" in policy
    assert "bug bounty" in policy


def test_scanner_decision_is_explicit_and_does_not_overclaim() -> None:
    decision = SELECTION_PATH.read_text(encoding="utf-8")

    assert "SECURITY-SCANNER-SELECTION@1.0.0" in decision
    assert "Selected scanner: Gitleaks `8.30.1`" in decision
    assert "TruffleHog 3.96.0" in decision
    assert "failed the pre-execution evidence-safety boundary" in decision
    assert "not a claim that TruffleHog is generally unsafe" in decision
    assert "does not prove" in decision
