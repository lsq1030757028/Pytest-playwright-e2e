from __future__ import annotations

import pytest

from test_workflow.harness import (
    BudgetAccount,
    BudgetExceededError,
    BudgetUsage,
    CapabilityAccess,
    CapabilityDescriptor,
    CapabilityRequest,
    ContextLevel,
    ContextRequest,
    ExecutionBudget,
    PermissionScope,
    PolicyEngine,
    PolicyOutcome,
    PolicyReason,
    scope_allows,
)


def descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name="target.materialize",
        version="1.0.0",
        default_context=ContextRequest(level=ContextLevel.SUMMARY),
        required_permissions=PermissionScope(
            read=frozenset({"targets/manifests/*"}),
            write=frozenset({"workspaces/targets/*"}),
            execute=frozenset({"git"}),
            network_domains=frozenset({"github.com"}),
            allow_subprocess=True,
        ),
        access=CapabilityAccess(allow_network=True, allow_subprocess=True),
        timeout_seconds=20,
    )


def allowed_request() -> CapabilityRequest:
    return CapabilityRequest(
        request_id="request-policy-allow",
        capability=descriptor().ref,
        context_request=ContextRequest(level=ContextLevel.METADATA),
        budget=ExecutionBudget(api_calls=1, subprocesses=1, wall_time_seconds=30),
        permissions=PermissionScope(
            read=frozenset({"targets/manifests/*"}),
            write=frozenset({"workspaces/*"}),
            execute=frozenset({"git"}),
            network_domains=frozenset({"github.com"}),
            allow_subprocess=True,
        ),
    )


def test_scope_allows_exact_and_trailing_prefix_only() -> None:
    assert scope_allows({"artifacts/spec/*"}, "artifacts/spec/TODO-1")
    assert scope_allows({"git"}, "git")
    assert not scope_allows({"artifacts/spec/*"}, "artifacts/secret/TODO-1")


def test_policy_allows_minimal_explicit_request() -> None:
    decision, event = PolicyEngine().evaluate(descriptor(), allowed_request())
    assert decision.outcome == PolicyOutcome.ALLOW
    assert event.event_type == "policy.allowed"
    assert not event.payload["reasons"]


def test_policy_denies_missing_permissions_and_budget() -> None:
    request = allowed_request().model_copy(
        update={
            "permissions": PermissionScope(),
            "budget": ExecutionBudget(wall_time_seconds=5),
        }
    )
    decision, event = PolicyEngine().evaluate(descriptor(), request)

    assert not decision.allowed
    assert PolicyReason.READ_SCOPE_MISSING in decision.reasons
    assert PolicyReason.NETWORK_SCOPE_MISSING in decision.reasons
    assert PolicyReason.SUBPROCESS_ACCESS_DENIED in decision.reasons
    assert PolicyReason.BUDGET_TOO_LOW in decision.reasons
    assert PolicyReason.TIMEOUT_EXCEEDS_BUDGET in decision.reasons
    assert event.event_type == "policy.denied"


def test_policy_denies_context_escalation_and_secret_access() -> None:
    request = allowed_request().model_copy(
        update={
            "context_request": ContextRequest(
                level=ContextLevel.DEEP,
                allow_secrets=True,
            )
        }
    )
    decision, _ = PolicyEngine().evaluate(descriptor(), request)
    assert PolicyReason.CONTEXT_TOO_DEEP in decision.reasons
    assert PolicyReason.SECRET_ACCESS_DENIED in decision.reasons


def test_policy_denies_capability_mismatch() -> None:
    request = allowed_request().model_copy(
        update={"capability": {"name": "target.start", "version": "1.0.0"}}
    )
    decision, _ = PolicyEngine().evaluate(descriptor(), request)
    assert decision.reasons[0] == PolicyReason.CAPABILITY_MISMATCH


def test_budget_account_accumulates_usage_and_calculates_remaining() -> None:
    account = BudgetAccount(
        ExecutionBudget(
            model_calls=1,
            token_limit=100,
            api_calls=3,
            wall_time_seconds=10,
            artifact_bytes=1000,
        )
    )
    account.consume(BudgetUsage(api_calls=1, token_limit=25, wall_time_seconds=2))
    account.consume(BudgetUsage(api_calls=1, artifact_bytes=100))

    assert account.usage.api_calls == 2
    assert account.remaining().api_calls == 1
    assert account.remaining().token_limit == 75


def test_budget_account_rejects_overrun_without_mutating_usage() -> None:
    account = BudgetAccount(ExecutionBudget(api_calls=1, wall_time_seconds=5))
    account.consume(BudgetUsage(api_calls=1))

    with pytest.raises(BudgetExceededError, match="api_calls"):
        account.consume(BudgetUsage(api_calls=1))
    assert account.usage.api_calls == 1


def test_model_and_browser_access_require_permissions_and_budget() -> None:
    value = CapabilityDescriptor(
        name="ai.explore-page",
        version="1.0.0",
        required_permissions=PermissionScope(allow_model=True, allow_browser=True),
        access=CapabilityAccess(allow_model=True, allow_browser=True),
        timeout_seconds=10,
    )
    request = CapabilityRequest(
        request_id="request-ai",
        capability=value.ref,
        budget=ExecutionBudget(wall_time_seconds=10),
        permissions=PermissionScope(),
    )
    decision, _ = PolicyEngine().evaluate(value, request)

    assert PolicyReason.MODEL_ACCESS_DENIED in decision.reasons
    assert PolicyReason.BROWSER_ACCESS_DENIED in decision.reasons
    assert PolicyReason.BUDGET_TOO_LOW in decision.reasons
