from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UXMode(StrEnum):
    SHADOW = "SHADOW"
    ADVISORY = "ADVISORY"
    BLOCKING = "BLOCKING"


class UXVerdict(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class EvidenceLevel(StrEnum):
    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"


class FindingStatus(StrEnum):
    OBSERVED = "OBSERVED"
    SUPPORTED = "SUPPORTED"
    REPRODUCED = "REPRODUCED"
    PROVEN = "PROVEN"
    CONTROLLED = "CONTROLLED"
    DISMISSED = "DISMISSED"


class InteractionKind(StrEnum):
    NAVIGATE = "NAVIGATE"
    VIEW_PRESENTED = "VIEW_PRESENTED"
    ACTION_ATTEMPTED = "ACTION_ATTEMPTED"
    ACTION_SUCCEEDED = "ACTION_SUCCEEDED"
    ACTION_FAILED = "ACTION_FAILED"
    FEEDBACK_OBSERVED = "FEEDBACK_OBSERVED"
    FOCUS_CHANGED = "FOCUS_CHANGED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BACKTRACK = "BACKTRACK"
    REPEAT_ACTION = "REPEAT_ACTION"
    DEAD_END = "DEAD_END"
    RECOVERY_ATTEMPTED = "RECOVERY_ATTEMPTED"
    RECOVERY_SUCCEEDED = "RECOVERY_SUCCEEDED"
    JOURNEY_COMPLETED = "JOURNEY_COMPLETED"
    JOURNEY_ABANDONED = "JOURNEY_ABANDONED"


class PriorKnowledge(StrEnum):
    NOVICE = "NOVICE"
    RETURNING = "RETURNING"
    EXPERT = "EXPERT"
    INTERRUPTED = "INTERRUPTED"


class JourneyExecutor(StrEnum):
    TODO_ADD = "TODO_ADD"
    TODO_RETURNING_FILTER_PERSISTENCE = "TODO_RETURNING_FILTER_PERSISTENCE"
    TODO_KEYBOARD_PRIMARY = "TODO_KEYBOARD_PRIMARY"
    TODO_INTERRUPTED_RESUME = "TODO_INTERRUPTED_RESUME"


class SyntheticUserProfile(FrozenModel):
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    revision: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    prior_knowledge: PriorKnowledge
    goal_comprehension_level: str = Field(min_length=1)
    exploration_tendency: str = Field(min_length=1)
    error_recovery_behavior: str = Field(min_length=1)
    input_preferences: tuple[str, ...] = Field(min_length=1)
    accessibility_constraints: tuple[str, ...] = ()
    attention_and_interruption_model: str = Field(min_length=1)
    action_selection_policy_ref: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        forbidden = {
            "inferred_race",
            "inferred_health_condition",
            "inferred_religion",
            "inferred_sexual_orientation",
            "biometric_emotion",
        }
        present = forbidden.intersection(value)
        if present:
            raise ValueError(f"sensitive Synthetic User fields are forbidden: {sorted(present)}")
        return value

    @property
    def ref(self) -> str:
        return f"{self.profile_id}@{self.revision}"


class DeviceProfile(FrozenModel):
    viewport_width: int = Field(ge=320, le=7680)
    viewport_height: int = Field(ge=240, le=4320)
    device_scale_factor: float = Field(ge=0.5, le=4)
    browser_engine: Literal["chromium"] = "chromium"
    input_modes: tuple[str, ...] = Field(min_length=1)
    prefers_reduced_motion: bool = False
    zoom_percent: int = Field(default=100, ge=50, le=400)


class LocaleTimezone(FrozenModel):
    locale: str = Field(min_length=2)
    timezone: str = Field(min_length=1)
    date_number_currency_format: str = Field(min_length=1)


class NetworkProfile(FrozenModel):
    latency_ms: int = Field(default=0, ge=0)
    download_kbps: int = Field(default=100000, ge=1)
    upload_kbps: int = Field(default=100000, ge=1)
    offline_schedule: tuple[str, ...] = ()
    failure_injections: tuple[str, ...] = ()


class AccessibilityContext(FrozenModel):
    keyboard_only: bool = False
    screen_reader_semantics: bool = True
    focus_visibility_required: bool = True
    contrast_profile: str = "DEFAULT"
    motion_constraints: str = "NONE"


class AccountDataState(FrozenModel):
    fixture_ref: str = Field(min_length=1)
    synthetic_fixture_only: bool = True
    production_account: bool = False

    @model_validator(mode="after")
    def reject_production_state(self) -> AccountDataState:
        if not self.synthetic_fixture_only or self.production_account:
            raise ValueError("Synthetic User runtime accepts synthetic fixture state only")
        return self


class UXBudgets(FrozenModel):
    max_steps: int = Field(ge=1, le=200)
    max_backtracks: int = Field(ge=0, le=50)
    max_retries: int = Field(ge=0, le=20)
    time_budget_seconds: int = Field(ge=1, le=1800)
    context_budget_units: int = Field(ge=1)


class ExperienceEnvironment(FrozenModel):
    environment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    revision: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    schema_version: str = "1.0.0"
    persona_revision: str
    journey_revision: str
    requirement_revision: str
    design_system_revision: str
    code_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    fixture_revision: str
    browser_revision: str
    playwright_revision: str
    evaluator_revision: str
    capability_versions: dict[str, str] = Field(min_length=1)
    random_seed: int
    device_profile: DeviceProfile
    locale_timezone: LocaleTimezone
    network_profile: NetworkProfile
    accessibility_context: AccessibilityContext
    prior_knowledge: PriorKnowledge
    account_and_data_state: AccountDataState
    budgets: UXBudgets

    @property
    def ref(self) -> str:
        return f"{self.environment_id}@{self.revision}"


class ExperienceOracle(FrozenModel):
    oracle_id: str
    revision: str
    journey_goal: str = Field(min_length=1)
    business_value: str = Field(min_length=1)
    start_state: str = Field(min_length=1)
    required_checkpoints: tuple[str, ...] = Field(min_length=1)
    success_outcomes: tuple[str, ...] = Field(min_length=1)
    forbidden_outcomes: tuple[str, ...] = Field(min_length=1)
    required_feedback: tuple[str, ...] = Field(min_length=1)
    recovery_expectations: tuple[str, ...] = ()
    accessibility_obligations: tuple[str, ...] = ()
    max_steps: int = Field(ge=1)
    max_backtracks: int = Field(ge=0)
    evidence_requirements: tuple[str, ...] = Field(min_length=1)
    severity_floor: str
    authority_refs: tuple[str, ...] = Field(min_length=1)

    @property
    def ref(self) -> str:
        return f"{self.oracle_id}@{self.revision}"


class EvaluatorOnly(FrozenModel):
    hidden_expected_actions: tuple[str, ...] = ()
    scoring_key: str = Field(min_length=1)
    disallowed_shortcuts: tuple[str, ...] = ()
    mutation_identity: str | None = None


class UXJourney(FrozenModel):
    journey_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    revision: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    executor: JourneyExecutor
    oracle: ExperienceOracle
    persona_refs: tuple[str, ...] = Field(min_length=1)
    environment_refs: tuple[str, ...] = Field(min_length=1)
    start_fixture_ref: str
    allowed_capabilities: tuple[str, ...] = Field(min_length=1)
    required_observations: tuple[str, ...] = Field(min_length=1)
    cleanup_and_recovery: str
    evaluator_only: EvaluatorOnly

    @property
    def ref(self) -> str:
        return f"{self.journey_id}@{self.revision}"


class UXCatalog(FrozenModel):
    catalog_id: str
    version: str
    spec_ref: str
    profiles: tuple[SyntheticUserProfile, ...] = Field(min_length=1)
    environments: tuple[ExperienceEnvironment, ...] = Field(min_length=1)
    journeys: tuple[UXJourney, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog_refs(self) -> UXCatalog:
        profile_refs = [item.ref for item in self.profiles]
        environment_refs = [item.ref for item in self.environments]
        journey_refs = [item.ref for item in self.journeys]
        for label, refs in (
            ("profile", profile_refs),
            ("environment", environment_refs),
            ("journey", journey_refs),
        ):
            if len(refs) != len(set(refs)):
                raise ValueError(f"duplicate UX {label} references")
        for environment in self.environments:
            if environment.persona_revision not in profile_refs:
                raise ValueError(
                    f"environment references unknown persona: {environment.persona_revision}"
                )
            if environment.journey_revision not in journey_refs:
                raise ValueError(
                    f"environment references unknown journey: {environment.journey_revision}"
                )
        for journey in self.journeys:
            if not set(journey.persona_refs).issubset(profile_refs):
                raise ValueError(f"journey {journey.ref} references an unknown persona")
            if not set(journey.environment_refs).issubset(environment_refs):
                raise ValueError(f"journey {journey.ref} references an unknown environment")
        return self


class UXCampaignPins(FrozenModel):
    code_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    target_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    catalog_revision: str
    playwright_revision: str
    browser_revision: str
    evaluator_revision: str
    random_seed: int


class UXCampaignPlan(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    spec_ref: str
    approval_ref: str
    mandate_ref: str
    mode: UXMode = UXMode.SHADOW
    catalog_path: str
    target_manifest_path: str
    journey_ids: tuple[str, ...] = ("*",)
    pins: UXCampaignPins
    human_uat_required: bool = True

    @model_validator(mode="after")
    def enforce_shadow_contract(self) -> UXCampaignPlan:
        if not self.spec_ref.startswith("SPEC-UX0-SYNTHETIC-USER@"):
            raise ValueError("UX campaign must reference the approved UX0 SPEC")
        if not self.approval_ref.startswith("APPROVAL-UX0-SYNTHETIC-USER-SPEC@"):
            raise ValueError("UX campaign must reference the UX0 approval event")
        if not self.mandate_ref.startswith("MANDATE-AUTONOMY-M1-M3@"):
            raise ValueError("UX campaign must reference the active autonomy mandate")
        if self.mode != UXMode.SHADOW:
            raise ValueError("UX0 Shadow Runner cannot enable advisory or blocking mode")
        if not self.human_uat_required:
            raise ValueError("Synthetic User Shadow Runner cannot replace Human UAT")
        return self


class ActorJourneyInput(FrozenModel):
    journey_id: str
    journey_revision: str
    user_goal: str
    profile: SyntheticUserProfile
    environment_ref: str
    allowed_capabilities: tuple[str, ...]
    max_steps: int
    max_backtracks: int


class UXEvent(FrozenModel):
    event_id: str
    sequence: int = Field(ge=1)
    kind: InteractionKind
    semantic_target_ref: str
    before_state_hash: str
    after_state_hash: str
    observable_result: str
    evidence_refs: tuple[str, ...] = ()


class UXMetrics(FrozenModel):
    task_completed: bool
    checkpoint_completed: int = Field(ge=0)
    checkpoint_total: int = Field(ge=0)
    step_count: int = Field(ge=0)
    backtrack_count: int = Field(ge=0)
    repeated_action_count: int = Field(ge=0)
    dead_end_count: int = Field(ge=0)
    recovery_success: bool | None = None
    feedback_observed: bool
    keyboard_completion: bool | None = None
    focus_order_violations: int = Field(default=0, ge=0)
    semantic_accessibility_failures: int = Field(default=0, ge=0)
    unexpected_state_loss: bool = False


class AICandidateFinding(FrozenModel):
    finding_id: str
    status: Literal[FindingStatus.OBSERVED] = FindingStatus.OBSERVED
    category: str
    observation_refs: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    affected_oracle_clause_refs: tuple[str, ...] = ()
    proposed_severity: str
    uncertainty: float = Field(ge=0, le=1)
    alternative_explanations: tuple[str, ...] = Field(min_length=1)
    suggested_followup: str = Field(min_length=1)
    blocking: Literal[False] = False


class UXEvaluation(FrozenModel):
    verdict: UXVerdict
    evidence_level: EvidenceLevel
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocker: bool = False

    @model_validator(mode="after")
    def validate_blocking_evidence(self) -> UXEvaluation:
        if self.blocker and self.evidence_level not in {EvidenceLevel.E3, EvidenceLevel.E4}:
            raise ValueError("UX blocker requires E3 or E4 evidence")
        return self


class UXJourneyRun(FrozenModel):
    run_id: str
    journey_ref: str
    profile_ref: str
    environment_ref: str
    environment_hash: str
    actor_input_hash: str
    target_revision: str
    events: tuple[UXEvent, ...]
    checkpoint_results: dict[str, bool]
    metrics: UXMetrics
    findings: tuple[AICandidateFinding, ...]
    evaluation: UXEvaluation
    evidence_path: str


class UXCampaignReport(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    spec_ref: str
    approval_ref: str
    mandate_ref: str
    mode: UXMode
    pins: UXCampaignPins
    runs: tuple[UXJourneyRun, ...]
    verdict: UXVerdict
    release_effect: Literal["NONBLOCKING_SHADOW"] = "NONBLOCKING_SHADOW"
    human_uat_required: Literal[True] = True
    semantic_digest: str


class UXArtifactManifest(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    files: dict[str, str]
    manifest_digest: str


class UXReplayManifest(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    spec_ref: str
    approval_ref: str
    semantic_digest: str
    artifact_manifest_digest: str
    input_files: dict[str, str]
