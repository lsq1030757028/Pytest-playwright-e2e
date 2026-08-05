from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from threading import RLock

from pydantic import Field

from .contracts import (
    CapabilityDescriptor,
    CapabilityRequest,
    ContextLevel,
    DomainEvent,
    EventSeverity,
    ExecutionBudget,
    FrozenModel,
    PermissionScope,
)


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyReason(StrEnum):
    CAPABILITY_MISMATCH = "capability_mismatch"
    CONTEXT_TOO_DEEP = "context_too_deep"
    SECRET_ACCESS_DENIED = "secret_access_denied"
    READ_SCOPE_MISSING = "read_scope_missing"
    WRITE_SCOPE_MISSING = "write_scope_missing"
    EXECUTE_SCOPE_MISSING = "execute_scope_missing"
    NETWORK_SCOPE_MISSING = "network_scope_missing"
    MODEL_ACCESS_DENIED = "model_access_denied"
    BROWSER_ACCESS_DENIED = "browser_access_denied"
    SUBPROCESS_ACCESS_DENIED = "subprocess_access_denied"
    BUDGET_TOO_LOW = "budget_too_low"
    TIMEOUT_EXCEEDS_BUDGET = "timeout_exceeds_budget"


class PolicyDecision(FrozenModel):
    outcome: PolicyOutcome
    reasons: tuple[PolicyReason, ...] = ()
    details: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.outcome == PolicyOutcome.ALLOW


class BudgetUsage(FrozenModel):
    model_calls: int = Field(default=0, ge=0)
    token_limit: int = Field(default=0, ge=0)
    browser_sessions: int = Field(default=0, ge=0)
    api_calls: int = Field(default=0, ge=0)
    subprocesses: int = Field(default=0, ge=0)
    wall_time_seconds: float = Field(default=0, ge=0)
    artifact_bytes: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)


class BudgetExceededError(RuntimeError):
    pass


class BudgetAccount:
    def __init__(self, limit: ExecutionBudget) -> None:
        self.limit = limit
        self._usage = BudgetUsage()
        self._lock = RLock()

    @property
    def usage(self) -> BudgetUsage:
        with self._lock:
            return self._usage

    def consume(self, delta: BudgetUsage) -> BudgetUsage:
        with self._lock:
            candidate = _add_usage(self._usage, delta)
            violations = budget_violations(self.limit, candidate)
            if violations:
                raise BudgetExceededError(", ".join(violations))
            self._usage = candidate
            return self._usage

    def remaining(self) -> ExecutionBudget:
        with self._lock:
            return ExecutionBudget(
                model_calls=self.limit.model_calls - self._usage.model_calls,
                token_limit=self.limit.token_limit - self._usage.token_limit,
                browser_sessions=self.limit.browser_sessions - self._usage.browser_sessions,
                api_calls=self.limit.api_calls - self._usage.api_calls,
                subprocesses=self.limit.subprocesses - self._usage.subprocesses,
                wall_time_seconds=self.limit.wall_time_seconds - self._usage.wall_time_seconds,
                artifact_bytes=self.limit.artifact_bytes - self._usage.artifact_bytes,
                retries=self.limit.retries - self._usage.retries,
            )


class PermissionGuard:
    def evaluate(
        self,
        descriptor: CapabilityDescriptor,
        request: CapabilityRequest,
    ) -> PolicyDecision:
        reasons: list[PolicyReason] = []
        details: list[str] = []
        if request.capability != descriptor.ref:
            reasons.append(PolicyReason.CAPABILITY_MISMATCH)
            details.append(
                f"request targets {request.capability.canonical_name}, "
                f"descriptor is {descriptor.ref.canonical_name}"
            )

        if _context_rank(request.context_request.level) > _context_rank(
            descriptor.default_context.level
        ):
            reasons.append(PolicyReason.CONTEXT_TOO_DEEP)
            details.append(
                f"requested {request.context_request.level}, "
                f"descriptor default is {descriptor.default_context.level}"
            )

        if request.context_request.allow_secrets and not request.permissions.allow_secrets:
            reasons.append(PolicyReason.SECRET_ACCESS_DENIED)
            details.append("context requested secrets without permission")

        self._check_scope(
            descriptor.required_permissions.read,
            request.permissions.read,
            PolicyReason.READ_SCOPE_MISSING,
            reasons,
            details,
        )
        self._check_scope(
            descriptor.required_permissions.write,
            request.permissions.write,
            PolicyReason.WRITE_SCOPE_MISSING,
            reasons,
            details,
        )
        self._check_scope(
            descriptor.required_permissions.execute,
            request.permissions.execute,
            PolicyReason.EXECUTE_SCOPE_MISSING,
            reasons,
            details,
        )
        self._check_scope(
            descriptor.required_permissions.network_domains,
            request.permissions.network_domains,
            PolicyReason.NETWORK_SCOPE_MISSING,
            reasons,
            details,
        )

        if descriptor.access.allow_model and not request.permissions.allow_model:
            reasons.append(PolicyReason.MODEL_ACCESS_DENIED)
            details.append("model access required")
        if descriptor.access.allow_browser and not request.permissions.allow_browser:
            reasons.append(PolicyReason.BROWSER_ACCESS_DENIED)
            details.append("browser access required")
        if descriptor.access.allow_subprocess and not request.permissions.allow_subprocess:
            reasons.append(PolicyReason.SUBPROCESS_ACCESS_DENIED)
            details.append("subprocess access required")

        self._check_budget(descriptor, request.budget, reasons, details)
        return PolicyDecision(
            outcome=PolicyOutcome.DENY if reasons else PolicyOutcome.ALLOW,
            reasons=tuple(dict.fromkeys(reasons)),
            details=tuple(details),
        )

    @staticmethod
    def _check_scope(
        required: Iterable[str],
        granted: Iterable[str],
        reason: PolicyReason,
        reasons: list[PolicyReason],
        details: list[str],
    ) -> None:
        missing = [item for item in required if not scope_allows(granted, item)]
        if missing:
            reasons.append(reason)
            details.append(f"missing scope: {', '.join(sorted(missing))}")

    @staticmethod
    def _check_budget(
        descriptor: CapabilityDescriptor,
        budget: ExecutionBudget,
        reasons: list[PolicyReason],
        details: list[str],
    ) -> None:
        required: list[str] = []
        if descriptor.access.allow_model and budget.model_calls < 1:
            required.append("model_calls>=1")
        if descriptor.access.allow_browser and budget.browser_sessions < 1:
            required.append("browser_sessions>=1")
        if descriptor.access.allow_network and budget.api_calls < 1:
            required.append("api_calls>=1")
        if descriptor.access.allow_subprocess and budget.subprocesses < 1:
            required.append("subprocesses>=1")
        if required:
            reasons.append(PolicyReason.BUDGET_TOO_LOW)
            details.append("; ".join(required))
        if descriptor.timeout_seconds > budget.wall_time_seconds:
            reasons.append(PolicyReason.TIMEOUT_EXCEEDS_BUDGET)
            details.append(
                f"timeout {descriptor.timeout_seconds}s exceeds "
                f"wall-time budget {budget.wall_time_seconds}s"
            )


class PolicyEngine:
    def __init__(self, guard: PermissionGuard | None = None) -> None:
        self.guard = guard or PermissionGuard()

    def evaluate(
        self,
        descriptor: CapabilityDescriptor,
        request: CapabilityRequest,
    ) -> tuple[PolicyDecision, DomainEvent]:
        decision = self.guard.evaluate(descriptor, request)
        event = DomainEvent(
            event_id=f"policy-{request.request_id}",
            event_type="policy.allowed" if decision.allowed else "policy.denied",
            source=descriptor.ref,
            payload={
                "request_id": request.request_id,
                "reasons": [item.value for item in decision.reasons],
                "details": list(decision.details),
            },
            severity=EventSeverity.INFO if decision.allowed else EventSeverity.ERROR,
            campaign_id=request.campaign_id,
            correlation_id=request.correlation_id,
        )
        return decision, event


def scope_allows(granted: Iterable[str], required: str) -> bool:
    for item in granted:
        if item == required:
            return True
        if item.endswith("/*"):
            prefix = item[:-1]
            if required.startswith(prefix):
                return True
    return False


def budget_violations(
    limit: ExecutionBudget,
    usage: BudgetUsage,
) -> tuple[str, ...]:
    checks: tuple[tuple[str, int | float, int | float], ...] = (
        ("model_calls", usage.model_calls, limit.model_calls),
        ("token_limit", usage.token_limit, limit.token_limit),
        ("browser_sessions", usage.browser_sessions, limit.browser_sessions),
        ("api_calls", usage.api_calls, limit.api_calls),
        ("subprocesses", usage.subprocesses, limit.subprocesses),
        ("wall_time_seconds", usage.wall_time_seconds, limit.wall_time_seconds),
        ("artifact_bytes", usage.artifact_bytes, limit.artifact_bytes),
        ("retries", usage.retries, limit.retries),
    )
    return tuple(
        f"{name}: used {used}, limit {maximum}"
        for name, used, maximum in checks
        if used > maximum
    )


def permissions_cover(granted: PermissionScope, required: PermissionScope) -> bool:
    return (
        all(scope_allows(granted.read, item) for item in required.read)
        and all(scope_allows(granted.write, item) for item in required.write)
        and all(scope_allows(granted.execute, item) for item in required.execute)
        and all(
            scope_allows(granted.network_domains, item)
            for item in required.network_domains
        )
        and (not required.allow_model or granted.allow_model)
        and (not required.allow_browser or granted.allow_browser)
        and (not required.allow_subprocess or granted.allow_subprocess)
        and (not required.allow_secrets or granted.allow_secrets)
    )


def _context_rank(level: ContextLevel) -> int:
    return {
        ContextLevel.METADATA: 0,
        ContextLevel.SUMMARY: 1,
        ContextLevel.FOCUSED: 2,
        ContextLevel.DEEP: 3,
    }[level]


def _add_usage(left: BudgetUsage, right: BudgetUsage) -> BudgetUsage:
    return BudgetUsage(
        model_calls=left.model_calls + right.model_calls,
        token_limit=left.token_limit + right.token_limit,
        browser_sessions=left.browser_sessions + right.browser_sessions,
        api_calls=left.api_calls + right.api_calls,
        subprocesses=left.subprocesses + right.subprocesses,
        wall_time_seconds=left.wall_time_seconds + right.wall_time_seconds,
        artifact_bytes=left.artifact_bytes + right.artifact_bytes,
        retries=left.retries + right.retries,
    )
