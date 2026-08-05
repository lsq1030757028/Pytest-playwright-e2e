from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from .integrity import sha256_file
from .serialization import load_document, load_model
from .specs import (
    EnvironmentSpec,
    MockDecision,
    MockPlan,
    TestSpec,
    ValidationIssue,
    ValidationReport,
)
from .virtual_service import load_behavior


def _error(code: str, message: str, path: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, path=path)


def validate_mock_configuration(bundle_root: str | Path) -> ValidationReport:
    root = Path(bundle_root).resolve()
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    try:
        test_spec = load_model(root / "spec" / "test-spec.yaml", TestSpec)
        environment = load_model(
            root / "environment" / "environment-spec.yaml", EnvironmentSpec
        )
        mock_plan = load_model(root / environment.mock_plan_path, MockPlan)
    except (OSError, ValueError) as exc:
        return ValidationReport(
            valid=False,
            errors=[_error("document.invalid", str(exc))],
        )

    if test_spec.truth_boundary != mock_plan.truth_boundary:
        errors.append(
            _error(
                "truth_boundary.mismatch",
                "TestSpec and MockPlan truth boundaries differ",
                "environment/mock-plan.yaml",
            )
        )

    must_be_real = set(test_spec.truth_boundary.must_be_real)
    may_be_mocked = set(test_spec.truth_boundary.may_be_mocked)
    decisions = {item.dependency: item for item in mock_plan.dependencies}

    for dependency in mock_plan.dependencies:
        if dependency.decision in {MockDecision.VIRTUALIZE, MockDecision.CONTROL}:
            if dependency.dependency in must_be_real:
                errors.append(
                    _error(
                        "truth_boundary.mocked_real_component",
                        f"{dependency.dependency} is required to be real",
                        dependency.dependency,
                    )
                )
            if dependency.dependency not in may_be_mocked:
                errors.append(
                    _error(
                        "truth_boundary.undeclared_mock",
                        f"{dependency.dependency} is not declared in may_be_mocked",
                        dependency.dependency,
                    )
                )

        if dependency.decision == MockDecision.NEEDS_CONFIRMATION:
            warnings.append(
                _error(
                    "mock.needs_confirmation",
                    f"{dependency.dependency} has no approved execution strategy",
                    dependency.dependency,
                )
            )

        if dependency.contract is not None:
            contract_path = root / dependency.contract.path
            if not contract_path.is_file():
                errors.append(
                    _error(
                        "contract.missing",
                        f"contract not found: {dependency.contract.path}",
                        dependency.contract.path,
                    )
                )
                continue
            actual_hash = sha256_file(contract_path)
            if actual_hash != dependency.contract.sha256:
                errors.append(
                    _error(
                        "contract.hash_mismatch",
                        f"expected {dependency.contract.sha256}, got {actual_hash}",
                        dependency.contract.path,
                    )
                )

        if dependency.behavior_path:
            behavior_path = root / dependency.behavior_path
            if not behavior_path.is_file():
                errors.append(
                    _error(
                        "mock.behavior_missing",
                        f"behavior not found: {dependency.behavior_path}",
                        dependency.behavior_path,
                    )
                )
                continue
            try:
                behavior = load_behavior(behavior_path)
            except ValueError as exc:
                errors.append(
                    _error("mock.behavior_invalid", str(exc), dependency.behavior_path)
                )
                continue
            if behavior.service != dependency.dependency:
                errors.append(
                    _error(
                        "mock.service_mismatch",
                        (
                            f"behavior service {behavior.service!r} does not match "
                            f"{dependency.dependency!r}"
                        ),
                        dependency.behavior_path,
                    )
                )
            if dependency.contract is not None:
                schema = load_document(root / dependency.contract.path)
                Draft202012Validator.check_schema(schema)
                response_validator = Draft202012Validator(schema)
                for route in behavior.routes:
                    for contract_error in response_validator.iter_errors(
                        route.response.json_body
                    ):
                        errors.append(
                            _error(
                                "contract.response_invalid",
                                f"route {route.id}: {contract_error.message}",
                                dependency.behavior_path,
                            )
                        )

    for service in environment.virtual_services:
        dependency = decisions.get(service)
        if dependency is None:
            errors.append(
                _error(
                    "environment.virtual_service_unplanned",
                    f"virtual service {service} is missing from MockPlan",
                    service,
                )
            )
        elif dependency.decision != MockDecision.VIRTUALIZE:
            errors.append(
                _error(
                    "environment.virtual_service_wrong_decision",
                    f"virtual service {service} must use decision=virtualize",
                    service,
                )
            )

    for service in environment.real_services:
        dependency = decisions.get(service)
        if dependency and dependency.decision != MockDecision.REAL:
            errors.append(
                _error(
                    "environment.real_service_mocked",
                    f"real service {service} has decision={dependency.decision}",
                    service,
                )
            )

    return ValidationReport(valid=not errors, errors=errors, warnings=warnings)
