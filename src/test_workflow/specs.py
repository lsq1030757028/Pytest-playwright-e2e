from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Confidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Probability(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OracleSource(StrEnum):
    REQUIREMENT = "requirement"
    CONTRACT = "contract"
    STATE_MACHINE = "state_machine"
    UI = "ui"
    API = "api"
    DATABASE = "database"
    EVENT = "event"


class MockDecision(StrEnum):
    REAL = "real"
    VIRTUALIZE = "virtualize"
    CONTROL = "control"
    NEEDS_CONFIRMATION = "needs_confirmation"


class RequirementSource(BaseModel):
    id: str
    source: str
    locator: str | None = None
    sha256: str | None = None


class FactSpec(BaseModel):
    id: str
    statement: str
    source: str
    confidence: Confidence = Confidence.CONFIRMED


class AssumptionSpec(BaseModel):
    id: str
    statement: str
    basis: str
    confidence: Confidence
    reversible: bool = True
    confirmation_required: bool = False


class RiskSpec(BaseModel):
    id: str
    title: str
    probability: Probability
    impact: RiskLevel
    test_required: bool = True
    rationale: str | None = None


class ActionSpec(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class OracleSpec(BaseModel):
    id: str
    source: OracleSource
    expression: str
    expected: Any | None = None
    basis_ref: str
    confidence: Confidence = Confidence.CONFIRMED


class TruthBoundary(BaseModel):
    must_be_real: list[str] = Field(default_factory=list)
    may_be_mocked: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_no_overlap(self) -> TruthBoundary:
        overlap = set(self.must_be_real) & set(self.may_be_mocked)
        if overlap:
            raise ValueError(f"truth boundary overlaps: {sorted(overlap)}")
        return self


class TestCaseSpec(BaseModel):
    id: str
    title: str
    risk: RiskLevel
    preconditions: list[str] = Field(default_factory=list)
    actions: list[ActionSpec]
    oracles: list[OracleSpec]
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_oracle_ids(self) -> TestCaseSpec:
        ids = [oracle.id for oracle in self.oracles]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate oracle ids in case {self.id}")
        return self


class TestSpec(BaseModel):
    schema_version: str = "1.0"
    id: str
    title: str
    requirement_sources: list[RequirementSource]
    facts: list[FactSpec] = Field(default_factory=list)
    assumptions: list[AssumptionSpec] = Field(default_factory=list)
    risks: list[RiskSpec] = Field(default_factory=list)
    truth_boundary: TruthBoundary
    cases: list[TestCaseSpec]
    regression_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> TestSpec:
        collections = {
            "requirement source": [item.id for item in self.requirement_sources],
            "fact": [item.id for item in self.facts],
            "assumption": [item.id for item in self.assumptions],
            "risk": [item.id for item in self.risks],
            "case": [item.id for item in self.cases],
        }
        for label, ids in collections.items():
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} ids")

        valid_basis = {
            *[item.id for item in self.requirement_sources],
            *[item.id for item in self.facts],
            *[item.id for item in self.assumptions],
        }
        for case in self.cases:
            for oracle in case.oracles:
                if oracle.basis_ref not in valid_basis:
                    raise ValueError(
                        f"oracle {oracle.id} references unknown basis {oracle.basis_ref}"
                    )
                if oracle.basis_ref.startswith("A-"):
                    assumption = next(
                        item for item in self.assumptions if item.id == oracle.basis_ref
                    )
                    if assumption.confirmation_required:
                        raise ValueError(
                            f"oracle {oracle.id} uses unconfirmed assumption {oracle.basis_ref}"
                        )
        return self


class ContractSpec(BaseModel):
    path: str
    sha256: str
    description: str | None = None


class MockDependencySpec(BaseModel):
    dependency: str
    decision: MockDecision
    reason: str
    risk: RiskLevel
    contract: ContractSpec | None = None
    behavior_path: str | None = None

    @model_validator(mode="after")
    def validate_virtualization_inputs(self) -> MockDependencySpec:
        if self.decision == MockDecision.VIRTUALIZE:
            if self.contract is None:
                raise ValueError(f"virtualized dependency {self.dependency} needs a contract")
            if not self.behavior_path:
                raise ValueError(f"virtualized dependency {self.dependency} needs behavior_path")
        return self


class MockPlan(BaseModel):
    schema_version: str = "1.0"
    truth_boundary: TruthBoundary
    dependencies: list[MockDependencySpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_dependencies(self) -> MockPlan:
        dependencies = [item.dependency for item in self.dependencies]
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("duplicate mock dependencies")
        return self


class ClockSpec(BaseModel):
    frozen_at: datetime | None = None
    timezone: str = "UTC"


class EnvironmentSpec(BaseModel):
    schema_version: str = "1.0"
    profile: str
    base_url: HttpUrl | None = None
    clock: ClockSpec = Field(default_factory=ClockSpec)
    random_seed: int = 1
    real_services: list[str] = Field(default_factory=list)
    virtual_services: list[str] = Field(default_factory=list)
    data_seed_path: str
    mock_plan_path: str
    network_isolation: bool = True

    @model_validator(mode="after")
    def validate_service_partition(self) -> EnvironmentSpec:
        overlap = set(self.real_services) & set(self.virtual_services)
        if overlap:
            raise ValueError(f"services cannot be both real and virtual: {sorted(overlap)}")
        return self


class BrowserStorageSeed(BaseModel):
    origin: HttpUrl
    local_storage: dict[str, Any] = Field(default_factory=dict)


class DataFixtureSpec(BaseModel):
    factory: str
    alias: str
    params: dict[str, Any] = Field(default_factory=dict)


class DataSeedSpec(BaseModel):
    schema_version: str = "1.0"
    fixtures: list[DataFixtureSpec] = Field(default_factory=list)
    browser_storage: list[BrowserStorageSeed] = Field(default_factory=list)


class ReplayArtifact(BaseModel):
    path: str
    sha256: str
    role: str = "input"


class ReplayManifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    created_at: datetime
    command: list[str]
    browser: str = "chromium"
    python_version: str
    random_seed: int
    artifacts: list[ReplayArtifact]


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
