from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import Field, field_validator, model_validator

from .artifacts import ArtifactStore, StoreExecutionContext
from .contracts import (
    ArtifactRef,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    DomainEvent,
    ExecutionMetrics,
    FrozenModel,
)
from .policy import BudgetAccount, BudgetExceededError, BudgetUsage, PolicyEngine
from .registry import CapabilityNotFoundError, CapabilityRegistry

NODE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"


class PlanStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class PlanValidationError(ValueError):
    pass


class OrchestrationError(RuntimeError):
    pass


class NodeOutputBinding(FrozenModel):
    from_node: str = Field(pattern=NODE_ID_PATTERN)
    output_index: int = Field(default=0, ge=0)
    expected_type: str | None = None


class ExecutionNode(FrozenModel):
    node_id: str = Field(pattern=NODE_ID_PATTERN)
    request: CapabilityRequest
    depends_on: tuple[str, ...] = ()
    input_bindings: tuple[NodeOutputBinding, ...] = ()
    continue_on_failure: bool = False

    @field_validator("depends_on")
    @classmethod
    def validate_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("dependencies must be unique")
        return value

    @model_validator(mode="after")
    def validate_node(self) -> ExecutionNode:
        if self.node_id in self.depends_on:
            raise ValueError("node cannot depend on itself")
        bound_nodes = {item.from_node for item in self.input_bindings}
        if not bound_nodes.issubset(set(self.depends_on)):
            raise ValueError("input bindings must reference declared dependencies")
        return self


class ExecutionPlan(FrozenModel):
    plan_id: str = Field(min_length=1, max_length=128)
    nodes: tuple[ExecutionNode, ...]

    @model_validator(mode="after")
    def validate_plan(self) -> ExecutionPlan:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node ids must be unique")
        known = set(node_ids)
        missing = sorted(
            dependency
            for node in self.nodes
            for dependency in node.depends_on
            if dependency not in known
        )
        if missing:
            raise ValueError(f"unknown dependencies: {', '.join(missing)}")
        self.topological_order()
        return self

    def node_map(self) -> dict[str, ExecutionNode]:
        return {node.node_id: node for node in self.nodes}

    def topological_order(self) -> tuple[str, ...]:
        dependencies = {node.node_id: set(node.depends_on) for node in self.nodes}
        result: list[str] = []
        ready = sorted(node_id for node_id, deps in dependencies.items() if not deps)
        while ready:
            current = ready.pop(0)
            result.append(current)
            for node_id in sorted(dependencies):
                if current in dependencies[node_id]:
                    dependencies[node_id].remove(current)
                    if not dependencies[node_id] and node_id not in result and node_id not in ready:
                        ready.append(node_id)
            ready.sort()
        if len(result) != len(self.nodes):
            raise PlanValidationError("execution plan contains a dependency cycle")
        return tuple(result)

    def parallel_batches(self) -> tuple[tuple[str, ...], ...]:
        remaining = {node.node_id: set(node.depends_on) for node in self.nodes}
        completed: set[str] = set()
        batches: list[tuple[str, ...]] = []
        while remaining:
            batch = tuple(
                sorted(
                    node_id
                    for node_id, dependencies in remaining.items()
                    if dependencies.issubset(completed)
                )
            )
            if not batch:
                raise PlanValidationError("execution plan contains a dependency cycle")
            batches.append(batch)
            completed.update(batch)
            for node_id in batch:
                remaining.pop(node_id)
        return tuple(batches)

    def descendants(self, node_ids: Iterable[str]) -> frozenset[str]:
        selected = set(node_ids)
        changed = True
        while changed:
            changed = False
            for node in self.nodes:
                if node.node_id not in selected and set(node.depends_on).intersection(selected):
                    selected.add(node.node_id)
                    changed = True
        return frozenset(selected)


class NodeExecution(FrozenModel):
    node_id: str = Field(pattern=NODE_ID_PATTERN)
    status: NodeStatus = NodeStatus.PENDING
    result: CapabilityResult | None = None
    error: str | None = None
    attempts: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_state(self) -> NodeExecution:
        if self.status == NodeStatus.SUCCEEDED and self.result is None:
            raise ValueError("succeeded node requires a result")
        if self.status == NodeStatus.FAILED and not self.error:
            raise ValueError("failed node requires an error")
        if self.status == NodeStatus.BLOCKED and not self.error:
            raise ValueError("blocked node requires a reason")
        return self


class ExecutionCheckpoint(FrozenModel):
    plan_id: str
    status: PlanStatus
    nodes: tuple[NodeExecution, ...]
    events: tuple[DomainEvent, ...] = ()

    def node_map(self) -> dict[str, NodeExecution]:
        return {node.node_id: node for node in self.nodes}


class WorkflowCompiler:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def compile(self, plan_id: str, nodes: Iterable[ExecutionNode]) -> ExecutionPlan:
        plan = ExecutionPlan(plan_id=plan_id, nodes=tuple(nodes))
        for node in plan.nodes:
            descriptor = self.registry.descriptor(
                node.request.capability.name,
                node.request.capability.version,
            )
            if descriptor.ref != node.request.capability:
                raise PlanValidationError(
                    f"request capability mismatch for node {node.node_id}"
                )
        return plan


class Orchestrator:
    def __init__(
        self,
        registry: CapabilityRegistry,
        store: ArtifactStore,
        policy: PolicyEngine | None = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.policy = policy or PolicyEngine()

    def execute(
        self,
        plan: ExecutionPlan,
        checkpoint: ExecutionCheckpoint | None = None,
        *,
        max_nodes: int | None = None,
    ) -> ExecutionCheckpoint:
        states = self._initial_states(plan, checkpoint)
        events = list(checkpoint.events if checkpoint else ())
        executed = 0
        node_map = plan.node_map()

        for node_id in plan.topological_order():
            current = states[node_id]
            if current.status not in {NodeStatus.PENDING, NodeStatus.RUNNING}:
                continue
            if max_nodes is not None and executed >= max_nodes:
                return self._checkpoint(plan, states, events, PlanStatus.PAUSED)

            node = node_map[node_id]
            dependency_states = [states[item].status for item in node.depends_on]
            if any(
                status in {NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.SKIPPED}
                for status in dependency_states
            ):
                states[node_id] = NodeExecution(
                    node_id=node_id,
                    status=NodeStatus.SKIPPED,
                    error="dependency did not succeed",
                )
                continue

            states[node_id] = NodeExecution(
                node_id=node_id,
                status=NodeStatus.RUNNING,
                attempts=current.attempts + 1,
            )
            executed += 1
            try:
                capability = self.registry.resolve(
                    node.request.capability.name,
                    node.request.capability.version,
                )
                request = self._bind_request(node, states)
                decision, policy_event = self.policy.evaluate(capability.descriptor, request)
                events.append(policy_event)
                if not decision.allowed:
                    states[node_id] = NodeExecution(
                        node_id=node_id,
                        status=NodeStatus.BLOCKED,
                        error="; ".join(decision.details) or "policy denied execution",
                        attempts=current.attempts + 1,
                    )
                    continue

                context = StoreExecutionContext(self.store)
                result = capability.execute(request, context)
                self._validate_result(request, result)
                self._account(request, result.metrics)
                for artifact in result.artifacts:
                    if not self.store.exists(artifact.artifact_id):
                        raise OrchestrationError(
                            f"capability returned unpersisted artifact {artifact.artifact_id}"
                        )
                events.extend(context.events)
                events.extend(
                    item
                    for item in result.events
                    if item.event_id not in {event.event_id for event in context.events}
                )
                states[node_id] = self._result_state(
                    node_id,
                    result,
                    attempts=current.attempts + 1,
                )
            except (CapabilityNotFoundError, BudgetExceededError, Exception) as exc:
                states[node_id] = NodeExecution(
                    node_id=node_id,
                    status=NodeStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}",
                    attempts=current.attempts + 1,
                )
                if not node.continue_on_failure:
                    continue

        status = self._plan_status(states)
        return self._checkpoint(plan, states, events, status)

    @staticmethod
    def _initial_states(
        plan: ExecutionPlan,
        checkpoint: ExecutionCheckpoint | None,
    ) -> dict[str, NodeExecution]:
        if checkpoint is None:
            return {
                node.node_id: NodeExecution(node_id=node.node_id)
                for node in plan.nodes
            }
        if checkpoint.plan_id != plan.plan_id:
            raise OrchestrationError("checkpoint belongs to another plan")
        states = checkpoint.node_map()
        expected = {node.node_id for node in plan.nodes}
        if set(states) != expected:
            raise OrchestrationError("checkpoint nodes do not match execution plan")
        return states

    def _bind_request(
        self,
        node: ExecutionNode,
        states: dict[str, NodeExecution],
    ) -> CapabilityRequest:
        inputs = list(node.request.input_artifacts)
        for binding in node.input_bindings:
            source = states[binding.from_node]
            if source.result is None:
                raise OrchestrationError(
                    f"binding source {binding.from_node} has no result"
                )
            try:
                artifact = source.result.artifacts[binding.output_index]
            except IndexError as exc:
                raise OrchestrationError(
                    f"binding output {binding.output_index} missing on {binding.from_node}"
                ) from exc
            if binding.expected_type and artifact.artifact_type != binding.expected_type:
                raise OrchestrationError(
                    f"binding expected {binding.expected_type}, got {artifact.artifact_type}"
                )
            inputs.append(artifact)
        return node.request.model_copy(update={"input_artifacts": tuple(inputs)})

    @staticmethod
    def _validate_result(request: CapabilityRequest, result: CapabilityResult) -> None:
        if result.request_id != request.request_id:
            raise OrchestrationError("capability result request_id mismatch")

    @staticmethod
    def _account(request: CapabilityRequest, metrics: ExecutionMetrics) -> None:
        account = BudgetAccount(request.budget)
        account.consume(
            BudgetUsage(
                model_calls=metrics.model_calls,
                token_limit=metrics.tokens,
                browser_sessions=metrics.browser_sessions,
                api_calls=metrics.api_calls,
                subprocesses=metrics.subprocesses,
                wall_time_seconds=metrics.duration_ms / 1000,
                artifact_bytes=metrics.artifact_bytes,
                retries=metrics.retries,
            )
        )

    @staticmethod
    def _result_state(
        node_id: str,
        result: CapabilityResult,
        *,
        attempts: int,
    ) -> NodeExecution:
        if result.status == CapabilityResultStatus.SUCCESS:
            return NodeExecution(
                node_id=node_id,
                status=NodeStatus.SUCCEEDED,
                result=result,
                attempts=attempts,
            )
        if result.status == CapabilityResultStatus.SKIPPED:
            return NodeExecution(
                node_id=node_id,
                status=NodeStatus.SKIPPED,
                result=result,
                error=result.error,
                attempts=attempts,
            )
        if result.status == CapabilityResultStatus.BLOCKED:
            return NodeExecution(
                node_id=node_id,
                status=NodeStatus.BLOCKED,
                result=result,
                error="; ".join(result.blockers),
                attempts=attempts,
            )
        return NodeExecution(
            node_id=node_id,
            status=NodeStatus.FAILED,
            result=result,
            error=result.error or "capability failed",
            attempts=attempts,
        )

    @staticmethod
    def _plan_status(states: dict[str, NodeExecution]) -> PlanStatus:
        statuses = {item.status for item in states.values()}
        if NodeStatus.PENDING in statuses or NodeStatus.RUNNING in statuses:
            return PlanStatus.PAUSED
        if NodeStatus.FAILED in statuses:
            return PlanStatus.FAILED
        if NodeStatus.BLOCKED in statuses:
            return PlanStatus.BLOCKED
        if statuses.issubset({NodeStatus.SUCCEEDED, NodeStatus.SKIPPED}):
            return PlanStatus.SUCCEEDED
        return PlanStatus.FAILED

    @staticmethod
    def _checkpoint(
        plan: ExecutionPlan,
        states: dict[str, NodeExecution],
        events: list[DomainEvent],
        status: PlanStatus,
    ) -> ExecutionCheckpoint:
        return ExecutionCheckpoint(
            plan_id=plan.plan_id,
            status=status,
            nodes=tuple(states[node_id] for node_id in plan.topological_order()),
            events=tuple(_deduplicate_events(events)),
        )


def reset_checkpoint(
    plan: ExecutionPlan,
    checkpoint: ExecutionCheckpoint,
    invalidated_nodes: Iterable[str],
) -> ExecutionCheckpoint:
    if checkpoint.plan_id != plan.plan_id:
        raise OrchestrationError("checkpoint belongs to another plan")
    reset = plan.descendants(invalidated_nodes)
    known = set(plan.node_map())
    if not reset.issubset(known):
        missing = sorted(reset - known)
        raise OrchestrationError(f"unknown invalidated nodes: {', '.join(missing)}")
    states = checkpoint.node_map()
    updated = tuple(
        NodeExecution(node_id=node.node_id)
        if node.node_id in reset
        else states[node.node_id]
        for node in plan.nodes
    )
    return ExecutionCheckpoint(
        plan_id=plan.plan_id,
        status=PlanStatus.READY,
        nodes=updated,
        events=checkpoint.events,
    )


def _deduplicate_events(events: Iterable[DomainEvent]) -> list[DomainEvent]:
    result: list[DomainEvent] = []
    seen: set[str] = set()
    for event in events:
        if event.event_id not in seen:
            seen.add(event.event_id)
            result.append(event)
    return result
