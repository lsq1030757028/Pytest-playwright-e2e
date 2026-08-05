from __future__ import annotations

from pathlib import Path

import pytest

from test_workflow.harness import (
    ArtifactTypeRef,
    CapabilityDescriptor,
    CapabilityRef,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    ExecutionCheckpoint,
    ExecutionNode,
    FileArtifactStore,
    NodeOutputBinding,
    Orchestrator,
    PlanStatus,
    StoreExecutionContext,
    WorkflowCompiler,
)


class SeedCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="fixture.seed",
            version="1.0.0",
            output_types=(ArtifactTypeRef(name="SeedData", schema_version=1),),
            timeout_seconds=1,
        )

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        ref = context.write_artifact(
            artifact_id="campaigns/golden/seed/v1",
            artifact_type="SeedData",
            schema_version=1,
            content={"items": ["active", "completed"]},
            created_by=self.descriptor.ref,
        )
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.SUCCESS,
            artifacts=(ref,),
        )


class PlanCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="test.plan",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="SeedData", schema_version=1),),
            output_types=(ArtifactTypeRef(name="TestPlan", schema_version=1),),
            timeout_seconds=1,
        )

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        seed = context.read_artifact(request.input_artifacts[0])
        ref = context.write_artifact(
            artifact_id="campaigns/golden/plan/v1",
            artifact_type="TestPlan",
            schema_version=1,
            content={"selected": len(seed["items"]), "deep_context_loaded": False},
            created_by=self.descriptor.ref,
        )
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.SUCCESS,
            artifacts=(ref,),
        )


def request(capability: str, request_id: str) -> CapabilityRequest:
    return CapabilityRequest(
        request_id=request_id,
        capability=CapabilityRef(name=capability, version="1.0.0"),
        campaign_id="CAMPAIGN-GOLDEN-HARNESS",
    )


@pytest.mark.harness_integration
def test_file_backed_orchestrator_pauses_serializes_and_resumes(tmp_path: Path) -> None:
    registry = CapabilityRegistry()
    registry.register(SeedCapability())
    registry.register(PlanCapability())
    plan = WorkflowCompiler(registry).compile(
        "golden-harness-plan",
        (
            ExecutionNode(node_id="seed", request=request("fixture.seed", "request-seed")),
            ExecutionNode(
                node_id="plan",
                request=request("test.plan", "request-plan"),
                depends_on=("seed",),
                input_bindings=(
                    NodeOutputBinding(
                        from_node="seed",
                        expected_type="SeedData",
                    ),
                ),
            ),
        ),
    )
    store_path = tmp_path / "artifact-store"
    checkpoint_path = tmp_path / "checkpoint.json"
    first = Orchestrator(registry, FileArtifactStore(store_path)).execute(plan, max_nodes=1)
    checkpoint_path.write_text(first.model_dump_json(indent=2), encoding="utf-8")

    restored = ExecutionCheckpoint.model_validate_json(
        checkpoint_path.read_text(encoding="utf-8")
    )
    completed = Orchestrator(registry, FileArtifactStore(store_path)).execute(plan, restored)
    output = completed.node_map()["plan"].result.artifacts[0]  # type: ignore[union-attr]

    assert first.status == PlanStatus.PAUSED
    assert completed.status == PlanStatus.SUCCEEDED
    assert FileArtifactStore(store_path).get(output).content == {
        "selected": 2,
        "deep_context_loaded": False,
    }
    assert completed.node_map()["seed"].attempts == 1
