from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemoryCondition(StrEnum):
    OFF = "MEMORY_OFF"
    CANDIDATE = "MEMORY_ON_CANDIDATE"
    VERIFIED = "MEMORY_ON_VERIFIED"
    ADVERSARIAL = "MEMORY_ON_ADVERSARIAL"


class MemoryAuthority(StrEnum):
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    REFERENCE = "REFERENCE"


class MemoryValidity(StrEnum):
    VALID = "VALID"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    CONFLICTING = "CONFLICTING"
    TAMPERED = "TAMPERED"


class RunStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class BenchmarkVerdict(StrEnum):
    PASS = "PASS"
    PASS_WITH_LIMITS = "PASS_WITH_LIMITS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


class MinimumRepetitions(FrozenModel):
    deterministic: int = Field(ge=1)
    stochastic: int = Field(ge=0)


class ScenarioContract(FrozenModel):
    required_fields: tuple[str, ...] = Field(min_length=1)


class MemoryScenario(FrozenModel):
    id: str = Field(pattern=r"^MEM-S[0-9]{3}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    family: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    threats: tuple[str, ...] = Field(min_length=1)
    protected_assets: tuple[str, ...] = Field(min_length=1)
    conditions: tuple[MemoryCondition, ...] = Field(min_length=1)
    preconditions: tuple[str, ...] = Field(min_length=1)
    perturbation: str = Field(min_length=1)
    oracle: str = Field(min_length=1)
    expected_safe_outcome: str = Field(min_length=1)
    disallowed_outcome: str = Field(min_length=1)
    required_evidence: tuple[str, ...] = Field(min_length=1)
    minimum_repetitions: MinimumRepetitions
    failure_classification: str = Field(min_length=1)
    future_modules: tuple[str, ...] = Field(min_length=1)


class ScenarioCatalog(FrozenModel):
    catalog_id: str
    version: str
    spec_ref: str
    status: str
    scenario_contract: ScenarioContract
    scenarios: tuple[MemoryScenario, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scenarios(self) -> ScenarioCatalog:
        ids = [scenario.id for scenario in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("memory scenario ids must be unique")
        expected = [f"MEM-S{index:03d}" for index in range(1, len(ids) + 1)]
        if ids != expected:
            raise ValueError("memory scenario ids must be ordered and contiguous")
        return self


class CurrentRequirement(FrozenModel):
    id: str
    revision: str
    text: str = Field(min_length=1)

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.revision}"


class ActorIdentity(FrozenModel):
    agent_id: str
    project_namespace: str
    readable_namespaces: tuple[str, ...]
    writable_namespaces: tuple[str, ...] = ()


class MemoryRecord(FrozenModel):
    id: str
    revision: str
    namespace: str
    authority: MemoryAuthority
    validity: MemoryValidity = MemoryValidity.VALID
    content: str = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)
    flags: tuple[str, ...] = ()
    acl_readers: tuple[str, ...] = ("*",)
    acl_writers: tuple[str, ...] = ()
    token_cost: int = Field(default=20, ge=1)

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.revision}"


class AttemptedOperation(FrozenModel):
    operation: Literal["read", "write", "promote", "forget", "rollback"]
    memory_ref: str
    namespace: str


class EvaluatorFixture(FrozenModel):
    expected_safe_action: str
    disallowed_actions: tuple[str, ...] = Field(min_length=1)
    answer_markers: tuple[str, ...] = ()
    expected_selected_by_condition: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    expected_filtered_reasons: dict[str, str] = Field(default_factory=dict)


class ScenarioFixture(FrozenModel):
    scenario_id: str = Field(pattern=r"^MEM-S[0-9]{3}$")
    version: str = "1.0.0"
    actor_task: str = Field(min_length=1)
    current_requirement: CurrentRequirement
    actor: ActorIdentity
    memory_records: tuple[MemoryRecord, ...] = ()
    attempted_operations: tuple[AttemptedOperation, ...] = ()
    context_token_budget: int = Field(default=160, ge=1)
    evaluator_only: EvaluatorFixture

    @model_validator(mode="after")
    def validate_record_refs(self) -> ScenarioFixture:
        refs = [record.ref for record in self.memory_records]
        if len(refs) != len(set(refs)):
            raise ValueError(f"fixture {self.scenario_id} has duplicate memory refs")
        return self


class FixtureCatalog(FrozenModel):
    fixture_catalog_id: str
    version: str
    spec_ref: str
    fixtures: tuple[ScenarioFixture, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fixtures(self) -> FixtureCatalog:
        ids = [fixture.scenario_id for fixture in self.fixtures]
        if len(ids) != len(set(ids)):
            raise ValueError("memory fixture scenario ids must be unique")
        return self


class BenchmarkPins(FrozenModel):
    requirement_revision: str
    code_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    task_fixture_revision: str
    model_provider_profile: str
    capability_versions: dict[str, str]
    tool_versions: dict[str, str]
    environment_revision: str
    random_seed: int
    time_budget_seconds: int = Field(ge=1)
    cost_budget_units: int = Field(ge=1)
    evaluator_version: str


class MemoryBenchmarkPlan(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    spec_ref: str
    mandate_ref: str
    catalog_path: str
    fixture_catalog_path: str
    scenario_ids: tuple[str, ...] = ("*",)
    deterministic_repetitions: int = Field(default=3, ge=3, le=20)
    provider_profile: str = "deterministic-safe-v1"
    pins: BenchmarkPins

    @model_validator(mode="after")
    def validate_refs(self) -> MemoryBenchmarkPlan:
        if not self.spec_ref.startswith("SPEC-M1.0-MEMORY-BENCHMARK@"):
            raise ValueError("M1.0 benchmark plan must reference the approved Memory SPEC")
        if not self.mandate_ref.startswith("MANDATE-AUTONOMY-M1-M3@"):
            raise ValueError("M1.0 benchmark plan must reference the active autonomy mandate")
        return self


class MemoryView(FrozenModel):
    ref: str
    namespace: str
    authority: MemoryAuthority
    validity: MemoryValidity
    content: str
    source_refs: tuple[str, ...]
    flags: tuple[str, ...]
    token_cost: int


class ActorInput(FrozenModel):
    scenario_id: str
    family: str
    condition: MemoryCondition
    actor_task: str
    current_requirement_ref: str
    current_requirement_text: str
    actor_id: str
    project_namespace: str
    visible_memories: tuple[MemoryView, ...]
    attempted_operations: tuple[AttemptedOperation, ...]
    context_token_budget: int


class FilteredMemory(FrozenModel):
    ref: str
    reason: str


class RetrievalPlan(FrozenModel):
    scenario_id: str
    condition: MemoryCondition
    store_revision_ref: str
    candidate_count: int = Field(ge=0)
    selected_memory_refs: tuple[str, ...]
    filtered: tuple[FilteredMemory, ...]
    used_tokens: int = Field(ge=0)
    token_budget: int = Field(ge=1)
    ranking_inputs: dict[str, Any]
    plan_hash: str


class ContextAssemblyManifest(FrozenModel):
    scenario_id: str
    current_requirement_ref: str
    selected_memory_refs: tuple[str, ...]
    excluded_evaluator_fields: tuple[str, ...]
    content_hash: str


class ActorDecision(FrozenModel):
    action: str
    used_memory_refs: tuple[str, ...] = ()
    claims: tuple[str, ...] = ()
    attempted_writes: tuple[str, ...] = ()
    authority_claims: dict[str, str] = Field(default_factory=dict)


class EvaluationResult(FrozenModel):
    passed: bool
    safe_outcome: bool
    failures: tuple[str, ...] = ()
    failure_classification: str | None = None
    critical_false_green: bool = False
    contamination_detected: bool = False


class RunMetrics(FrozenModel):
    correct: bool
    intervention_required: bool
    token_count: int = Field(ge=0)
    cost_units: int = Field(ge=0)
    latency_units: int = Field(ge=0)


class BenchmarkRun(FrozenModel):
    run_id: str
    scenario_id: str
    scenario_version: str
    family: str
    condition: MemoryCondition
    attempt: int = Field(ge=1)
    status: RunStatus
    pins: BenchmarkPins
    actor_input_hash: str
    retrieval_plan: RetrievalPlan
    context_manifest: ContextAssemblyManifest
    decision: ActorDecision
    evaluation: EvaluationResult
    metrics: RunMetrics
    evidence_path: str


class MetricDelta(FrozenModel):
    scenario_id: str
    correctness_percentage_points: float
    intervention_reduction_percent: float
    token_reduction_percent: float
    cost_reduction_percent: float


class SafetySummary(FrozenModel):
    total_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    blocked_runs: int = Field(ge=0)
    invalid_runs: int = Field(ge=0)
    critical_false_green_count: int = Field(ge=0)
    unauthorized_scope_read_count: int = Field(ge=0)
    unauthorized_memory_write_count: int = Field(ge=0)
    assumption_to_authority_count: int = Field(ge=0)
    contamination_count: int = Field(ge=0)


class CampaignReport(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    spec_ref: str
    mandate_ref: str
    provider_profile: str
    pins: BenchmarkPins
    scenario_count: int = Field(ge=0)
    runs: tuple[BenchmarkRun, ...]
    metric_deltas: tuple[MetricDelta, ...]
    safety: SafetySummary
    value_gate_passed: bool
    verdict: BenchmarkVerdict
    closes_memory_gate: bool = False
    semantic_digest: str


class ArtifactManifest(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    files: dict[str, str]
    manifest_digest: str


class BenchmarkReplayManifest(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    spec_ref: str
    mandate_ref: str
    semantic_digest: str
    artifact_manifest_digest: str
    input_files: dict[str, str]
