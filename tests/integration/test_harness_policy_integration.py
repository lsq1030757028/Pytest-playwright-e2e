from __future__ import annotations

import pytest

from test_workflow.harness import (
    BudgetAccount,
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
)


@pytest.mark.harness_integration
def test_policy_gate_authorizes_then_accounts_for_a_bounded_operation() -> None:
    descriptor = CapabilityDescriptor(
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
    request = CapabilityRequest(
        request_id="policy-golden",
        capability=descriptor.ref,
        context_request=ContextRequest(level=ContextLevel.METADATA),
        budget=ExecutionBudget(
            api_calls=1,
            subprocesses=1,
            wall_time_seconds=30,
            artifact_bytes=1000,
        ),
        permissions=PermissionScope(
            read=frozenset({"targets/manifests/*"}),
            write=frozenset({"workspaces/*"}),
            execute=frozenset({"git"}),
            network_domains=frozenset({"github.com"}),
            allow_subprocess=True,
        ),
        campaign_id="CAMPAIGN-HARNESS-001",
    )

    decision, event = PolicyEngine().evaluate(descriptor, request)
    account = BudgetAccount(request.budget)
    usage = account.consume(
        BudgetUsage(
            api_calls=1,
            subprocesses=1,
            wall_time_seconds=3,
            artifact_bytes=120,
        )
    )

    assert decision.outcome == PolicyOutcome.ALLOW
    assert event.campaign_id == request.campaign_id
    assert usage.api_calls == 1
    assert account.remaining().subprocesses == 0
    assert account.remaining().artifact_bytes == 880
