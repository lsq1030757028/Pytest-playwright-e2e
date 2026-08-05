from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .models import (
    ActorJourneyInput,
    AICandidateFinding,
    EvidenceLevel,
    ExperienceEnvironment,
    FindingStatus,
    SyntheticUserProfile,
    UXEvaluation,
    UXJourney,
    UXMetrics,
    UXVerdict,
)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def environment_digest(environment: ExperienceEnvironment) -> str:
    return canonical_digest(environment.model_dump(mode="json"))


def build_actor_input(
    journey: UXJourney,
    profile: SyntheticUserProfile,
    environment: ExperienceEnvironment,
) -> ActorJourneyInput:
    return ActorJourneyInput(
        journey_id=journey.journey_id,
        journey_revision=journey.revision,
        user_goal=journey.oracle.journey_goal,
        profile=profile,
        environment_ref=environment.ref,
        allowed_capabilities=journey.allowed_capabilities,
        max_steps=environment.budgets.max_steps,
        max_backtracks=environment.budgets.max_backtracks,
    )


def evaluate_journey(
    journey: UXJourney,
    checkpoint_results: Mapping[str, bool],
    metrics: UXMetrics,
    *,
    evidence_integrity: bool = True,
) -> UXEvaluation:
    if not evidence_integrity:
        return UXEvaluation(
            verdict=UXVerdict.INVALID,
            evidence_level=EvidenceLevel.E3,
            failures=("evidence_integrity_failed",),
            blocker=False,
        )
    missing = tuple(
        checkpoint
        for checkpoint in journey.oracle.required_checkpoints
        if not checkpoint_results.get(checkpoint, False)
    )
    failures: list[str] = []
    warnings: list[str] = []
    if missing:
        failures.extend(f"checkpoint_failed:{item}" for item in missing)
    if not metrics.task_completed:
        failures.append("critical_journey_not_completed")
    if metrics.unexpected_state_loss:
        failures.append("unexpected_state_loss")
    if metrics.keyboard_completion is False:
        failures.append("keyboard_task_blocked")
    if metrics.semantic_accessibility_failures:
        failures.append("semantic_accessibility_task_block")
    if metrics.recovery_success is False:
        failures.append("recovery_failed")
    if metrics.step_count > journey.oracle.max_steps:
        failures.append("authoritative_step_budget_exceeded")
    if metrics.backtrack_count > journey.oracle.max_backtracks:
        failures.append("authoritative_backtrack_budget_exceeded")
    if not metrics.feedback_observed:
        warnings.append("required_feedback_not_observed")

    if failures:
        return UXEvaluation(
            verdict=UXVerdict.FAIL,
            evidence_level=EvidenceLevel.E3,
            failures=tuple(failures),
            warnings=tuple(warnings),
            blocker=True,
        )
    if warnings:
        return UXEvaluation(
            verdict=UXVerdict.WARN,
            evidence_level=EvidenceLevel.E2,
            warnings=tuple(warnings),
            blocker=False,
        )
    return UXEvaluation(
        verdict=UXVerdict.PASS,
        evidence_level=EvidenceLevel.E3,
        blocker=False,
    )


class RuleBasedUXCritic:
    profile = "deterministic-ux-critic-v1"

    def propose(
        self,
        *,
        journey: UXJourney,
        metrics: UXMetrics,
        event_refs: Sequence[str],
        evidence_refs: Sequence[str],
    ) -> tuple[AICandidateFinding, ...]:
        findings: list[AICandidateFinding] = []
        if not metrics.feedback_observed:
            findings.append(
                AICandidateFinding(
                    finding_id=f"{journey.journey_id}:feedback",
                    status=FindingStatus.OBSERVED,
                    category="feedback_clarity",
                    observation_refs=tuple(event_refs) or ("journey:no-event",),
                    evidence_refs=tuple(evidence_refs) or ("evidence:missing",),
                    affected_oracle_clause_refs=(
                        f"{journey.oracle.ref}:required_feedback",
                    ),
                    proposed_severity="P2",
                    uncertainty=0.25,
                    alternative_explanations=(
                        "The state change may itself be sufficient feedback for this design.",
                    ),
                    suggested_followup=(
                        "Replay with a novice profile and verify the required feedback clause."
                    ),
                    blocking=False,
                )
            )
        if metrics.backtrack_count or metrics.repeated_action_count:
            findings.append(
                AICandidateFinding(
                    finding_id=f"{journey.journey_id}:friction",
                    status=FindingStatus.OBSERVED,
                    category="interaction_friction",
                    observation_refs=tuple(event_refs) or ("journey:no-event",),
                    evidence_refs=tuple(evidence_refs) or ("evidence:missing",),
                    affected_oracle_clause_refs=(f"{journey.oracle.ref}:friction",),
                    proposed_severity="P3",
                    uncertainty=0.4,
                    alternative_explanations=(
                        "The repeated action may be intentional exploration rather than confusion.",
                    ),
                    suggested_followup="Repeat with a fixed policy and compare event sequences.",
                    blocking=False,
                )
            )
        return tuple(findings)
