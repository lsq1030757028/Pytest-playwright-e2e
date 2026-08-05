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
    DomainEvent,
    ExecutionMetrics,
    FileArtifactStore,
    StoreExecutionContext,
)


class UppercaseCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="text.uppercase",
            version="1.0.0",
            input_types=(ArtifactTypeRef(name="TextInput", schema_version=1),),
            output_types=(ArtifactTypeRef(name="TextOutput", schema_version=1),),
        )

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        source = context.read_artifact(request.input_artifacts[0])
        output = context.write_artifact(
            artifact_id="outputs/uppercase/v1",
            artifact_type="TextOutput",
            schema_version=1,
            content={"value": source["value"].upper()},
            created_by=self.descriptor.ref,
            source_revisions={"input": request.input_artifacts[0].artifact_id},
        )
        event = DomainEvent(
            event_id="event-uppercase",
            event_type="capability.completed",
            source=self.descriptor.ref,
            payload={"output": output.artifact_id},
        )
        context.emit(event)
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.SUCCESS,
            artifacts=(output,),
            events=(event,),
            metrics=ExecutionMetrics(artifact_bytes=32),
        )


@pytest.mark.harness_integration
def test_registry_and_file_store_execute_a_versioned_capability(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "artifacts")
    input_ref = store.put(
        artifact_id="inputs/message/v1",
        artifact_type="TextInput",
        schema_version=1,
        content={"value": "hello harness"},
        created_by=CapabilityRef(name="source.register", version="1.0.0"),
    )
    registry = CapabilityRegistry()
    registry.register(UppercaseCapability())
    capability = registry.resolve("text.uppercase")
    context = StoreExecutionContext(store)

    result = capability.execute(
        CapabilityRequest(
            request_id="registry-integration",
            capability=capability.descriptor.ref,
            input_artifacts=(input_ref,),
        ),
        context,
    )

    assert result.status == CapabilityResultStatus.SUCCESS
    assert store.get(result.artifacts[0]).content == {"value": "HELLO HARNESS"}
    assert FileArtifactStore(tmp_path / "artifacts").get(result.artifacts[0]).content == {
        "value": "HELLO HARNESS"
    }
    assert context.events == [result.events[0]]
