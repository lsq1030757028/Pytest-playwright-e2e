from test_workflow.classifier import classify_failure
from test_workflow.models import FailureCategory, FailureEvidence


def test_classifies_stable_api_confirmed_failure_as_product_defect() -> None:
    result = classify_failure(
        FailureEvidence(
            test_id="test_boundary",
            exception_type="AssertionError",
            message="expected true, got false",
            stable_reproduction=True,
            api_confirms_wrong_result=True,
        )
    )

    assert result.category == FailureCategory.PRODUCT_DEFECT
    assert result.test_code_change_allowed is False


def test_classifies_locator_failure_as_test_defect() -> None:
    result = classify_failure(
        FailureEvidence(
            test_id="test_login",
            exception_type="Error",
            message="strict mode violation: locator resolved to 2 elements",
        )
    )

    assert result.category == FailureCategory.TEST_DEFECT
    assert result.test_code_change_allowed is True


def test_retry_pass_is_flaky_not_product_defect() -> None:
    result = classify_failure(
        FailureEvidence(
            test_id="test_eventual_status",
            retry_passed=True,
            stable_reproduction=True,
            api_confirms_wrong_result=True,
        )
    )

    assert result.category == FailureCategory.FLAKY
