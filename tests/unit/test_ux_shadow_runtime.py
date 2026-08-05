from pathlib import Path

import pytest
from pydantic import ValidationError

from test_workflow.ux.catalog import load_ux_campaign
from test_workflow.ux.evaluator import (
    RuleBasedUXCritic,
    build_actor_input,
    environment_digest,
    evaluate_journey,
)
from test_workflow.ux.models import (
    AccountDataState,
    EvidenceLevel,
    SyntheticUserProfile,
    UXCampaignPlan,
    UXCatalog,
    UXMetrics,
    UXMode,
    UXVerdict,
)

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "benchmarks/ux/ux0/campaign.yaml"
CODE_SHA = "a" * 40


def loaded_campaign(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UX_CODE_SHA", CODE_SHA)
    return load_ux_campaign(CAMPAIGN)


def test_campaign_loads_four_pinned_shadow_journeys(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = loaded_campaign(monkeypatch)

    assert loaded.plan.mode == UXMode.SHADOW
    assert loaded.plan.human_uat_required is True
    assert loaded.plan.pins.code_sha == CODE_SHA
    assert len(loaded.catalog.profiles) == 4
    assert len(loaded.catalog.environments) == 4
    assert [item.journey_id for item in loaded.catalog.journeys] == [
        "novice-add-task",
        "returning-filter-persistence",
        "keyboard-primary",
        "interrupted-resume",
    ]
    assert loaded.target_manifest.revision == loaded.plan.pins.target_revision


def test_environment_hash_is_stable_and_storage_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_campaign(monkeypatch)
    environment = loaded.catalog.environments[0]

    assert environment_digest(environment) == environment_digest(
        environment.model_copy(deep=True)
    )
    assert len(environment_digest(environment)) == 64
    assert "workspace" not in environment.model_dump(mode="json")
    assert "port" not in environment.model_dump(mode="json")


def test_actor_input_excludes_evaluator_only_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = loaded_campaign(monkeypatch)
    journey = loaded.catalog.journeys[0]
    profile = loaded.catalog.profiles[0]
    environment = loaded.catalog.environments[0]

    actor_input = build_actor_input(journey, profile, environment)
    payload = actor_input.model_dump(mode="json")
    serialized = actor_input.model_dump_json()

    assert payload["user_goal"] == journey.oracle.journey_goal
    assert "evaluator_only" not in payload
    assert journey.evaluator_only.scoring_key not in serialized
    assert "fill_new_todo_and_press_enter" not in serialized
    assert "direct_local_storage_write" not in serialized


def test_non_shadow_mode_and_human_uat_replacement_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_campaign(monkeypatch)
    payload = loaded.plan.model_dump(mode="json")
    payload["mode"] = "BLOCKING"
    with pytest.raises(ValidationError, match="cannot enable advisory or blocking"):
        UXCampaignPlan.model_validate(payload)

    payload["mode"] = "SHADOW"
    payload["human_uat_required"] = False
    with pytest.raises(ValidationError, match="cannot replace Human UAT"):
        UXCampaignPlan.model_validate(payload)


def test_sensitive_persona_and_production_account_are_rejected() -> None:
    profile_payload = {
        "profile_id": "invalid-profile",
        "revision": "1.0.0",
        "prior_knowledge": "NOVICE",
        "goal_comprehension_level": "BASIC",
        "exploration_tendency": "LOW",
        "error_recovery_behavior": "RETRY",
        "input_preferences": ["POINTER"],
        "accessibility_constraints": [],
        "attention_and_interruption_model": "CONTINUOUS",
        "action_selection_policy_ref": "deterministic-v1",
        "inferred_race": "forbidden",
    }
    with pytest.raises(ValidationError, match="sensitive Synthetic User fields"):
        SyntheticUserProfile.model_validate(profile_payload)

    with pytest.raises(ValidationError, match="synthetic fixture state only"):
        AccountDataState.model_validate(
            {
                "fixture_ref": "production-account",
                "synthetic_fixture_only": False,
                "production_account": True,
            }
        )


def test_catalog_rejects_unknown_persona_and_environment_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_campaign(monkeypatch)
    payload = loaded.catalog.model_dump(mode="json")
    payload["environments"][0]["persona_revision"] = "missing@1.0.0"
    with pytest.raises(ValidationError, match="unknown persona"):
        UXCatalog.model_validate(payload)


def test_deterministic_evaluator_requires_e3_for_blocking_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_campaign(monkeypatch)
    journey = loaded.catalog.journeys[0]
    metrics = UXMetrics(
        task_completed=False,
        checkpoint_completed=0,
        checkpoint_total=len(journey.oracle.required_checkpoints),
        step_count=1,
        backtrack_count=0,
        repeated_action_count=0,
        dead_end_count=0,
        feedback_observed=False,
    )
    evaluation = evaluate_journey(
        journey,
        {item: False for item in journey.oracle.required_checkpoints},
        metrics,
    )

    assert evaluation.verdict == UXVerdict.FAIL
    assert evaluation.blocker is True
    assert evaluation.evidence_level == EvidenceLevel.E3
    assert "critical_journey_not_completed" in evaluation.failures


def test_ai_critic_emits_nonblocking_candidate_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_campaign(monkeypatch)
    journey = loaded.catalog.journeys[0]
    metrics = UXMetrics(
        task_completed=True,
        checkpoint_completed=3,
        checkpoint_total=3,
        step_count=2,
        backtrack_count=0,
        repeated_action_count=0,
        dead_end_count=0,
        feedback_observed=False,
    )

    findings = RuleBasedUXCritic().propose(
        journey=journey,
        metrics=metrics,
        event_refs=("ux-event-001",),
        evidence_refs=("evidence/trace.zip",),
    )

    assert len(findings) == 1
    assert findings[0].status.value == "OBSERVED"
    assert findings[0].blocking is False
    assert findings[0].uncertainty > 0
    assert findings[0].alternative_explanations


def test_tampered_or_missing_campaign_environment_variable_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UX_CODE_SHA", raising=False)
    with pytest.raises(ValueError, match="UX_CODE_SHA"):
        load_ux_campaign(CAMPAIGN)
