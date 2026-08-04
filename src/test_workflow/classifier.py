from __future__ import annotations

from .models import FailureCategory, FailureClassification, FailureEvidence

_ENVIRONMENT_HINTS = (
    "connection refused",
    "name or service not known",
    "dns",
    "service unavailable",
    "net::err_",
    "target page, context or browser has been closed",
)
_TEST_HINTS = (
    "strict mode violation",
    "locator resolved to",
    "fixture",
    "no tests ran",
    "selector",
)
_DATA_HINTS = (
    "duplicate key",
    "already exists",
    "unique constraint",
    "test data",
)


def classify_failure(evidence: FailureEvidence) -> FailureClassification:
    message = f"{evidence.exception_type} {evidence.message}".lower()

    if evidence.requirement_ambiguous:
        return FailureClassification(
            test_id=evidence.test_id,
            category=FailureCategory.REQUIREMENT_CONFLICT,
            confidence=0.93,
            reason="Expected behavior is not uniquely defined by the available requirement.",
            test_code_change_allowed=False,
        )

    if evidence.retry_passed:
        return FailureClassification(
            test_id=evidence.test_id,
            category=FailureCategory.FLAKY,
            confidence=0.82,
            reason="The same revision and environment passed on retry; isolate and investigate timing or shared state.",
            test_code_change_allowed=True,
        )

    if evidence.duplicate_test_data or any(hint in message for hint in _DATA_HINTS):
        return FailureClassification(
            test_id=evidence.test_id,
            category=FailureCategory.TEST_DATA_DEFECT,
            confidence=0.9,
            reason="The failure is caused by colliding or invalid test data.",
            test_code_change_allowed=True,
        )

    if any(hint in message for hint in _ENVIRONMENT_HINTS) or any(
        status >= 500 for status in evidence.status_codes
    ):
        return FailureClassification(
            test_id=evidence.test_id,
            category=FailureCategory.ENVIRONMENT_DEFECT,
            confidence=0.86,
            reason="Connectivity, browser lifecycle, or upstream service evidence indicates an environment failure.",
            test_code_change_allowed=False,
        )

    if any(hint in message for hint in _TEST_HINTS):
        return FailureClassification(
            test_id=evidence.test_id,
            category=FailureCategory.TEST_DEFECT,
            confidence=0.84,
            reason="The evidence points to locator, fixture, collection, or test implementation behavior.",
            test_code_change_allowed=True,
        )

    if evidence.stable_reproduction and evidence.api_confirms_wrong_result:
        return FailureClassification(
            test_id=evidence.test_id,
            category=FailureCategory.PRODUCT_DEFECT,
            confidence=0.95,
            reason="The behavior reproduces consistently and is confirmed below the UI layer.",
            test_code_change_allowed=False,
        )

    return FailureClassification(
        test_id=evidence.test_id,
        category=FailureCategory.UNKNOWN,
        confidence=0.35,
        reason="The available evidence is insufficient for a safe automatic classification.",
        test_code_change_allowed=False,
    )
