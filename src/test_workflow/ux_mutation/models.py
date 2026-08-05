from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MutationFamily(StrEnum):
    MISSING_FEEDBACK = "MISSING_FEEDBACK"
    VISIBLE_SUCCESS_STATE_LOSS = "VISIBLE_SUCCESS_STATE_LOSS"
    KEYBOARD_FOCUS_SEMANTIC_BARRIER = "KEYBOARD_FOCUS_SEMANTIC_BARRIER"
    INTERRUPTED_RESUME_FAILURE = "INTERRUPTED_RESUME_FAILURE"
    FILTER_ROUTE_STATE_DRIFT = "FILTER_ROUTE_STATE_DRIFT"


class ProofPhase(StrEnum):
    BASELINE = "BASELINE"
    MUTATED = "MUTATED"
    RESTORED = "RESTORED"


class MutationOutcome(StrEnum):
    KILLED = "KILLED"
    SURVIVED = "SURVIVED"
    INVALID = "INVALID"
    BLOCKED = "BLOCKED"


class ProofCampaignVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID = "INVALID"
    BLOCKED = "BLOCKED"


class ProofState(StrEnum):
    PLANNED = "PLANNED"
    BASELINE_RUNNING = "BASELINE_RUNNING"
    BASELINE_PROVEN = "BASELINE_PROVEN"
    MUTATION_APPLYING = "MUTATION_APPLYING"
    MUTATION_VERIFIED = "MUTATION_VERIFIED"
    MUTATED_RUNNING = "MUTATED_RUNNING"
    MUTATION_KILLED = "MUTATION_KILLED"
    RESTORING = "RESTORING"
    RESTORE_VERIFIED = "RESTORE_VERIFIED"
    RESTORED_RUNNING = "RESTORED_RUNNING"
    CLOSED_PASS = "CLOSED_PASS"
    BASELINE_FAILED = "BASELINE_FAILED"
    MUTATION_APPLY_FAILED = "MUTATION_APPLY_FAILED"
    MUTATION_SURVIVED = "MUTATION_SURVIVED"
    RESTORE_FAILED = "RESTORE_FAILED"
    REPLAY_DRIFTED = "REPLAY_DRIFTED"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    BLOCKED = "BLOCKED"


class TargetMutableFile(FrozenModel):
    path: str
    git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")
    preimage_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_length: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_path(self) -> TargetMutableFile:
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("mutable target path must be relative without traversal")
        return self


class RequiredUnmodifiedFile(FrozenModel):
    path: str
    git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")


class MutationTarget(FrozenModel):
    target_id: str
    repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    target_manifest_path: str
    mutable_file: TargetMutableFile
    required_unmodified_files: tuple[RequiredUnmodifiedFile, ...] = ()


class MutationCatalogContract(FrozenModel):
    id_pattern: str
    application_type: Literal["EXACT_TEXT_REPLACE"]
    expected_replacement_count: Literal[1]
    regex_allowed: Literal[False]
    arbitrary_command_allowed: Literal[False]
    path_must_be_relative: Literal[True]
    path_traversal_forbidden: Literal[True]
    one_mutation_per_checkout: Literal[True]
    exact_preimage_required: Literal[True]
    exact_postimage_required: Literal[True]
    exact_restore_required: Literal[True]


class UXMutation(FrozenModel):
    mutation_id: str = Field(pattern=r"^UXM-[0-9]{3}$")
    family: MutationFamily
    title: str = Field(min_length=1)
    severity: Literal["CRITICAL"] = "CRITICAL"
    target_path: str
    preimage_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    search_text: str = Field(min_length=1)
    search_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replacement_text: str = Field(min_length=1)
    replacement_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_replacement_count: Literal[1] = 1
    postimage_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    affected_journey_refs: tuple[str, ...] = Field(min_length=1)
    oracle_refs: tuple[str, ...] = Field(min_length=1)
    expected_failed_checkpoints: tuple[str, ...] = Field(min_length=1)
    expected_failure_classification: str = Field(min_length=1)
    minimum_evidence_level: Literal["E3", "E4"]
    disallowed_kill_basis: Literal["AI_CANDIDATE_ONLY"]

    @model_validator(mode="after")
    def validate_mutation(self) -> UXMutation:
        path = Path(self.target_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("mutation target_path must remain inside target checkout")
        if self.search_text == self.replacement_text:
            raise ValueError("mutation replacement must change target content")
        return self


class UXMutationCatalog(FrozenModel):
    catalog_id: str
    version: str
    spec_ref: str
    status: str
    target: MutationTarget
    mutation_contract: MutationCatalogContract
    mutations: tuple[UXMutation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self) -> UXMutationCatalog:
        ids = [mutation.mutation_id for mutation in self.mutations]
        expected = [f"UXM-{index:03d}" for index in range(1, len(ids) + 1)]
        if ids != expected:
            raise ValueError("UX mutation ids must be ordered and contiguous")
        if len(ids) != len(set(ids)):
            raise ValueError("UX mutation ids must be unique")
        families = [mutation.family for mutation in self.mutations]
        if len(families) != len(set(families)):
            raise ValueError("first UX proof requires one mutation per family")
        if any(
            mutation.target_path != self.target.mutable_file.path
            for mutation in self.mutations
        ):
            raise ValueError("all UX1 mutations must target the declared mutable file")
        return self


class UXMutationProofPlan(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    spec_ref: str
    parent_runtime_ref: str
    mandate_ref: str
    mode: Literal["SHADOW"] = "SHADOW"
    release_effect: Literal["NONBLOCKING_SHADOW"] = "NONBLOCKING_SHADOW"
    human_uat_required: Literal[True] = True
    project_root: str = "."
    mutation_catalog_path: str
    ux_campaign_path: str
    mutation_ids: tuple[str, ...] = ("*",)

    @model_validator(mode="after")
    def validate_plan(self) -> UXMutationProofPlan:
        if not self.spec_ref.startswith("SPEC-UX1-TODOMVC-MUTATION-PROOF@"):
            raise ValueError("UX mutation proof must reference the approved UX1 SPEC")
        if not self.parent_runtime_ref.startswith("UX0-SYNTHETIC-USER-SHADOW@"):
            raise ValueError("UX mutation proof must reference the merged UX0 runtime")
        if not self.mandate_ref.startswith("MANDATE-AUTONOMY-M1-M3@"):
            raise ValueError("UX mutation proof must reference the active autonomy mandate")
        root = Path(self.project_root)
        if root.is_absolute():
            raise ValueError("project_root must be relative")
        return self


class ProofTransitionEvent(FrozenModel):
    event_id: str
    sequence: int = Field(ge=1)
    from_state: ProofState
    to_state: ProofState
    reason_code: str


class PatchEvidence(FrozenModel):
    target_path: str
    preimage_sha256: str
    search_sha256: str
    replacement_sha256: str
    observed_replacement_count: int = Field(ge=0)
    postimage_sha256: str
    changed_files: tuple[str, ...]
    restored_sha256: str | None = None
    restore_clean: bool = False


class PhaseEvidence(FrozenModel):
    phase: ProofPhase
    report_path: str
    report_semantic_digest: str
    verdict: str
    journey_refs: tuple[str, ...]
    actor_input_hashes: dict[str, str]
    failed_checkpoints: dict[str, tuple[str, ...]]
    target_file_sha256: str
    changed_files: tuple[str, ...]
    git_status_clean: bool


class MutationProofResult(FrozenModel):
    mutation_id: str
    family: MutationFamily
    title: str
    outcome: MutationOutcome
    terminal_state: ProofState
    transitions: tuple[ProofTransitionEvent, ...]
    baseline: PhaseEvidence | None = None
    patch: PatchEvidence | None = None
    mutated: PhaseEvidence | None = None
    restored: PhaseEvidence | None = None
    expected_failed_checkpoints: tuple[str, ...]
    observed_failed_checkpoints: tuple[str, ...]
    expected_failure_classification: str
    actor_input_consistent: bool
    exact_restore: bool
    replay_required: bool = True
    failures: tuple[str, ...] = ()
    evidence_path: str


class MutationCampaignMetrics(FrozenModel):
    total_mutations: int = Field(ge=0)
    killed_mutations: int = Field(ge=0)
    survived_mutations: int = Field(ge=0)
    invalid_mutations: int = Field(ge=0)
    blocked_mutations: int = Field(ge=0)
    critical_mutation_kill_rate_percent: float = Field(ge=0, le=100)
    baseline_false_positive_count: int = Field(ge=0)
    critical_false_green_count: int = Field(ge=0)
    exact_restore_percent: float = Field(ge=0, le=100)
    replay_percent: float = Field(ge=0, le=100)
    oracle_clause_coverage_percent: float = Field(ge=0, le=100)
    journey_coverage_percent: float = Field(ge=0, le=100)
    hidden_metadata_leakage_count: int = Field(ge=0)
    undeclared_changed_files_count: int = Field(ge=0)
    ai_only_kill_count: int = Field(ge=0)


class UXMutationCampaignReport(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    spec_ref: str
    parent_runtime_ref: str
    mandate_ref: str
    mode: Literal["SHADOW"] = "SHADOW"
    release_effect: Literal["NONBLOCKING_SHADOW"] = "NONBLOCKING_SHADOW"
    human_uat_required: Literal[True] = True
    target_id: str
    target_revision: str
    mutation_results: tuple[MutationProofResult, ...]
    metrics: MutationCampaignMetrics
    verdict: ProofCampaignVerdict
    semantic_digest: str


class UXMutationArtifactManifest(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    files: dict[str, str]
    manifest_digest: str


class UXMutationReplayManifest(FrozenModel):
    schema_version: str = "1.0"
    campaign_id: str
    spec_ref: str
    parent_runtime_ref: str
    semantic_digest: str
    artifact_manifest_digest: str
    input_files: dict[str, str]
