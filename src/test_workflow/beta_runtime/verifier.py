from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import ArtifactStore


@dataclass(frozen=True)
class VerificationInput:
    required_node_ids: tuple[str, ...]
    collected_node_ids: tuple[str, ...]
    runtime_report_path: Path
    command_exit_code: int
    artifact_refs: tuple[dict[str, Any], ...]
    product_source_unchanged: bool
    cleanup_verified: bool
    policy_conflict: str | None = None
    oracle_conflict: str | None = None
    infrastructure_error: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    verdict: str
    terminal_state: str
    reason: str
    required_nodes: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "terminal_state": self.terminal_state,
            "reason": self.reason,
            "required_nodes": self.required_nodes,
        }


def _load_reports(path: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if not path.is_file():
        return reports
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        value = json.loads(raw)
        if isinstance(value, dict):
            reports.append(value)
    return reports


def _required_outcomes(required: tuple[str, ...], reports: list[dict[str, Any]]) -> dict[str, str]:
    outcomes = {node: "NOT_EXECUTED" for node in required}
    for report in reports:
        node_id = report.get("nodeid")
        if node_id not in outcomes:
            continue
        phase = report.get("when")
        outcome = str(report.get("outcome", "unknown")).upper()
        if phase in {"setup", "teardown"} and outcome == "FAILED":
            outcomes[node_id] = f"{phase.upper()}_FAILED"
        elif phase == "call":
            outcomes[node_id] = outcome
    return outcomes


def verify_attempt(value: VerificationInput, store: ArtifactStore) -> VerificationResult:
    required = set(value.required_node_ids)
    collected = set(value.collected_node_ids)
    if not required <= collected:
        missing = sorted(required - collected)
        return VerificationResult(
            verdict="TEST_DEFECT",
            terminal_state="FAILED",
            reason=f"required nodes missing from collection: {missing}",
            required_nodes={node: "NOT_COLLECTED" for node in value.required_node_ids},
        )
    if value.policy_conflict:
        return VerificationResult(
            verdict="POLICY_BLOCKED",
            terminal_state="BLOCKED",
            reason=value.policy_conflict,
            required_nodes={},
        )
    if value.oracle_conflict:
        return VerificationResult(
            verdict="ORACLE_CONFLICT",
            terminal_state="BLOCKED",
            reason=value.oracle_conflict,
            required_nodes={},
        )
    if value.infrastructure_error:
        return VerificationResult(
            verdict="ENVIRONMENT_FAILURE",
            terminal_state="FAILED",
            reason=value.infrastructure_error,
            required_nodes={},
        )
    if not value.product_source_unchanged:
        return VerificationResult(
            verdict="POLICY_BLOCKED",
            terminal_state="BLOCKED",
            reason="product source changed during execution",
            required_nodes={},
        )
    if not value.cleanup_verified:
        return VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            terminal_state="BLOCKED",
            reason="workspace/process cleanup is not verified",
            required_nodes={},
        )
    if not value.artifact_refs or not all(store.verify(ref) for ref in value.artifact_refs):
        return VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            terminal_state="BLOCKED",
            reason="required artifact is missing or failed SHA-256 verification",
            required_nodes={},
        )

    try:
        reports = _load_reports(value.runtime_report_path)
    except (OSError, json.JSONDecodeError) as exc:
        return VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            terminal_state="BLOCKED",
            reason=f"runtime report is unreadable: {exc}",
            required_nodes={},
        )
    outcomes = _required_outcomes(value.required_node_ids, reports)
    failed = {node: outcome for node, outcome in outcomes.items() if outcome != "PASSED"}
    if failed:
        if any(outcome in {"NOT_EXECUTED", "SKIPPED", "XFAILED"} for outcome in failed.values()):
            verdict = "INSUFFICIENT_EVIDENCE"
            state = "BLOCKED"
            reason = "one or more required governed nodes did not execute and pass"
        elif any(outcome.endswith("_FAILED") for outcome in failed.values()):
            verdict = "TEST_DEFECT"
            state = "FAILED"
            reason = "required node setup/teardown failed"
        else:
            verdict = "PRODUCT_DEFECT"
            state = "FAILED"
            reason = "required governed assertion failed with bound Oracle"
        return VerificationResult(verdict, state, reason, outcomes)

    if value.command_exit_code != 0:
        return VerificationResult(
            verdict="ENVIRONMENT_FAILURE",
            terminal_state="FAILED",
            reason="test command exited non-zero without a required-node assertion failure",
            required_nodes=outcomes,
        )
    if not required:
        return VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            terminal_state="BLOCKED",
            reason="governed pack has no required nodes",
            required_nodes=outcomes,
        )
    return VerificationResult(
        verdict="VERIFIED_SUCCESS",
        terminal_state="SUCCEEDED",
        reason="all required nodes passed and required evidence verified",
        required_nodes=outcomes,
    )
