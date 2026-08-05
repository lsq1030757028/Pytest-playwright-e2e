from __future__ import annotations

import pytest
from pydantic import ValidationError

from test_workflow.harness import (
    ArtifactTypeRef,
    CapabilityDescriptor,
    CapabilityNotFoundError,
    CapabilityRef,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    ExecutionNode,
    ExecutionPlan,
    InMemoryArtifactStore,
    NodeOutputBinding,
    NodeStatus,
    Orchestrator,
    PlanStatus,
    StoreExecutionContext,
    WorkflowCompiler,
    reset_checkpoint,
)


class EmitCapability:
    def __init__(self, name: str, output_type: str, value: str) -> None:
        self.value = value
        self._descriptor = CapabilityDescriptor(
            name=name,
            version="1.0.0",
            output_types=(ArtifactTypeRef(name=output_type, schema_version=1),),
            timeout_seconds=1,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        ref = context.write_artifact(
            artifact_id=f"outputs/{self.descriptor.name}/{request.request_id}",
            artifact_type=self.descriptor.output_types[0].name,
            schema_version=1,
            content={"value": self.value},
            created_by=self.descriptor.ref,
        )
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.SUCCESS,
            artifacts=(ref,),
        )


class TransformCapability:
    def __init__(self) -> None:
        self._descriptor = CapabilityDescriptor(
            name="text.transform",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="TextInput", schema_version=1),),
            output_types=(ArtifactTypeRef(name="TextOutput", schema_version=1),),
            timeout_seconds=1,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        value = context.read_artifact(request.input_artifacts[0])["value"]
        ref = context.write_artifact(
            artifact_id=f"outputs/transform/{request.request_id}",
            artifact_type="TextOutput",
            schema_version=1,
            content={"value": value.upper()},
            created_by=self.descriptor.ref,
        )
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.SUCCESS,
            artifacts=(ref,),
        )


class FailingCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(name="test.fail", version="1.0.0", timeout_seconds=1)

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.FAILED,
            error="expected failure",
        )


def request(name: str, request_id: str) -> CapabilityRequest:
    return CapabilityRequest(
        request_id=request_id,
        capability=CapabilityRef(name=name, version="1.0.0"),
    )


def registry() -> CapabilityRegistry:
    value = CapabilityRegistry()
    value.register(EmitCapability("text.emit", "TextInput", "hello"))
    value.register(TransformCapability())
    value.register(FailingCapability())
    return value


def two_node_plan() -> ExecutionPlan:
    return WorkflowCompiler(registry()).compile(
        "plan-two-node",
        (
            ExecutionNode(node_id="emit", request=request("text.emit", "request-emit")),
            ExecutionNode(
                node_id="transform",
                request=request("text.transform", "request-transform"),
                depends_on=("emit",),
                input_bindings=(
                    NodeOutputBinding(
                        from_node="emit",
                        output_index=0,
                        expected_type="TextInput",
                    ),
                ),
            ),
        ),
    )


def test_plan_rejects_cycles_unknown_dependencies_and_binding_leaks() -> None:
    with pytest.raises(ValidationError, match="unknown dependencies"):
        ExecutionPlan(
            plan_id="missing",
            nodes=(
                ExecutionNode(
                    node_id="one",
                    request=request("text.emit", "request-one"),
                    depends_on=("missing",),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="cycle"):
        ExecutionPlan(
            plan_id="cycle",
            nodes=(
                ExecutionNode(
                    node_id="one",
                    request=request("text.emit", "request-one"),
                    depends_on=("two",),
                ),
                ExecutionNode(
                    node_id="two",
                    request=request("text.emit", "request-two"),
                    depends_on=("one",),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="declared dependencies"):
        ExecutionNode(
            node_id="transform",
            request=request("text.transform", "request-transform"),
            input_bindings=(NodeOutputBinding(from_node="emit"),),
        )


def test_plan_order_and_parallel_batches_are_deterministic() -> None:
    plan = ExecutionPlan(
        plan_id="parallel",
        nodes=(
            ExecutionNode(node_id="b", request=request("text.emit", "request-b")),
            ExecutionNode(node_id="a", request=request("text.emit", "request-a")),
            ExecutionNode(
                node_id="c",
                request=request("text.emit", "request-c"),
                depends_on=("a", "b"),
            ),
        ),
    )
    assert plan.topological_order() == ("a", "b", "c")
    assert plan.parallel_batches() == (("a", "b"), ("c",))


def test_compiler_requires_registered_exact_capability_version() -> None:
    with pytest.raises(CapabilityNotFoundError):
        WorkflowCompiler(registry()).compile(
            "missing-capability",
            (
                ExecutionNode(
                    node_id="missing",
                    request=request("missing.capability", "request-missing"),
                ),
            ),
        )


def test_orchestrator_executes_bound_artifact_chain() -> None:
    store = InMemoryArtifactStore()
    checkpoint = Orchestrator(registry(), store).execute(two_node_plan())

    states = checkpoint.node_map()
    assert checkpoint.status == PlanStatus.SUCCEEDED
    assert states["emit"].status == NodeStatus.SUCCEEDED
    assert states["transform"].status == NodeStatus.SUCCEEDED
    output = states["transform"].result.artifacts[0]  # type: ignore[union-attr]
    assert store.get(output).content == {"value": "HELLO"}


def test_orchestrator_pauses_and_resumes_without_rerunning_completed_node() -> None:
    orchestrator = Orchestrator(registry(), InMemoryArtifactStore())
    plan = two_node_plan()
    paused = orchestrator.execute(plan, max_nodes=1)
    resumed = orchestrator.execute(plan, paused)

    assert paused.status == PlanStatus.PAUSED
    assert paused.node_map()["emit"].attempts == 1
    assert paused.node_map()["transform"].status == NodeStatus.PENDING
    assert resumed.status == PlanStatus.SUCCEEDED
    assert resumed.node_map()["emit"].attempts == 1
    assert resumed.node_map()["transform"].attempts == 1


def test_reset_checkpoint_invalidates_node_and_descendants_only() -> None:
    orchestrator = Orchestrator(registry(), InMemoryArtifactStore())
    plan = two_node_plan()
    completed = orchestrator.execute(plan)
    reset = reset_checkpoint(plan, completed, ("transform",))

    assert reset.node_map()["emit"].status == NodeStatus.SUCCEEDED
    assert reset.node_map()["transform"].status == NodeStatus.PENDING


def test_failed_dependency_skips_descendant() -> None:
    value = registry()
    plan = WorkflowCompiler(value).compile(
        "failure-plan",
        (
            ExecutionNode(node_id="fail", request=request("test.fail", "request-fail")),
            ExecutionNode(
                node_id="after",
                request=request("text.emit", "request-after"),
                depends_on=("fail",),
            ),
        ),
    )
    checkpoint = Orchestrator(value, InMemoryArtifactStore()).execute(plan)

    assert checkpoint.status == PlanStatus.FAILED
    assert checkpoint.node_map()["fail"].status == NodeStatus.FAILED
    assert checkpoint.node_map()["after"].status == NodeStatus.SKIPPED
