from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import yaml

API_ROOT = "https://api.github.com"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fetch_json(url: str) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "beta-a-acceptance-evidence-verifier",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def verify_pull_request(repo: str, section: dict[str, Any]) -> dict[str, Any]:
    number = int(section["pull_request"])
    expected_commit = str(section["merge_commit"])
    pull = fetch_json(f"{API_ROOT}/repos/{repo}/pulls/{number}")
    if pull.get("state") != "closed" or pull.get("merged_at") is None:
        raise RuntimeError(f"PR #{number} is not merged")
    if pull.get("merge_commit_sha") != expected_commit:
        raise RuntimeError(
            f"PR #{number} merge commit mismatch: "
            f"{pull.get('merge_commit_sha')} != {expected_commit}"
        )
    return {
        "pull_request": number,
        "merge_commit": expected_commit,
        "merged": True,
    }


def verify_runs(repo: str, section: dict[str, Any]) -> list[dict[str, Any]]:
    expected_commit = str(section["merge_commit"])
    verified: list[dict[str, Any]] = []
    for label, binding in section["exact_main_runs"].items():
        run_id = int(binding["run_id"])
        expected_workflow = str(binding["workflow"])
        expected_conclusion = str(binding["conclusion"])
        run = fetch_json(f"{API_ROOT}/repos/{repo}/actions/runs/{run_id}")
        checks = {
            "head_sha": run.get("head_sha") == expected_commit,
            "head_branch": run.get("head_branch") == "main",
            "event": run.get("event") == "push",
            "workflow": run.get("name") == expected_workflow,
            "status": run.get("status") == "completed",
            "conclusion": run.get("conclusion") == expected_conclusion,
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise RuntimeError(
                f"run {run_id} ({label}) failed evidence checks: {', '.join(failed)}"
            )
        verified.append(
            {
                "label": label,
                "run_id": run_id,
                "workflow": expected_workflow,
                "head_sha": expected_commit,
                "conclusion": expected_conclusion,
            }
        )
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reverify GitHub evidence bound by BETA-A acceptance."
    )
    parser.add_argument(
        "evidence",
        nargs="?",
        default="docs/evidence/beta-a-acceptance.yaml",
    )
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is required")

    evidence = load_yaml(Path(args.evidence))
    sections = (
        evidence["implementation_truth"],
        evidence["implementation_closure_truth"],
        evidence["verified_main_truth"],
    )
    report = {
        "schema_version": "1.0",
        "acceptance_id": evidence["acceptance"]["id"],
        "candidate_status": evidence["acceptance"]["status"],
        "repository": repo,
        "pull_requests": [verify_pull_request(repo, section) for section in sections],
        "runs": [item for section in sections for item in verify_runs(repo, section)],
    }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
