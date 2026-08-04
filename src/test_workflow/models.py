from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FailureCategory(StrEnum):
    PRODUCT_DEFECT = "product_defect"
    TEST_DEFECT = "test_defect"
    ENVIRONMENT_DEFECT = "environment_defect"
    TEST_DATA_DEFECT = "test_data_defect"
    FLAKY = "flaky"
    REQUIREMENT_CONFLICT = "requirement_conflict"
    UNKNOWN = "unknown"


class QualityGate(StrEnum):
    PASS = "PASS"
    PASS_WITH_RISK = "PASS_WITH_RISK"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class PreflightResult(BaseModel):
    environment: str
    status: QualityGate
    checks: list[CheckResult]


class FailureEvidence(BaseModel):
    test_id: str
    exception_type: str = ""
    message: str = ""
    retry_passed: bool = False
    stable_reproduction: bool = False
    api_confirms_wrong_result: bool = False
    duplicate_test_data: bool = False
    requirement_ambiguous: bool = False
    status_codes: list[int] = Field(default_factory=list)


class FailureClassification(BaseModel):
    test_id: str
    category: FailureCategory
    confidence: float = Field(ge=0, le=1)
    reason: str
    test_code_change_allowed: bool
