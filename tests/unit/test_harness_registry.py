from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_workflow.harness import (
    ArtifactImmutableError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactTypeRef,
    CapabilityAlreadyRegisteredError,
    CapabilityDescriptor,
    CapabilityNotFoundError,
    CapabilityRef,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    FileArtifactStore,
    InMemoryArtifactStore,
    StoreExecutionContext,
    content_hash,
    semver_key,
)


class NoopCapability:
    def __init__(self, version: str) -> None:
        self._descriptor = CapabilityDescriptor(name="test.noop", version=version)

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def execute(
        self, request: CapabilityRequest, context: StoreExecutionContext
    ) -> CapabilityResult:
        return CapabilityResult(
            request_id=request.request_id,
            status=CapabilityResultStatus.SUCCESS,
        )


def test_registry_resolves_latest_stable_semver() -> None:
    registry = CapabilityRegistry()
    registry.register(NoopCapability("1.0.0"))
    registry.register(NoopCapability("1.2.0-beta.1"))
    registry.register(NoopCapability("1.1.0"))

    assert registry.resolve("test.noop").descriptor.version == "1.1.0"
    assert semver_key("1.1.0") > semver_key("1.1.0-beta.1")


def test_registry_rejects_duplicate_and_missing_capabilities() -> None:
    registry = CapabilityRegistry()
    capability = NoopCapability("1.0.0")
    registry.register(capability)

    with pytest.raises(CapabilityAlreadyRegisteredError):
        registry.register(capability)
    with pytest.raises(CapabilityNotFoundError):
        registry.resolve("missing")
    with pytest.raises(CapabilityNotFoundError):
        registry.resolve("test.noop", "2.0.0")


def test_registry_lists_descriptors_in_deterministic_order() -> None:
    registry = CapabilityRegistry()
    registry.register(NoopCapability("2.0.0"))
    registry.register(NoopCapability("1.0.0"))

    assert [item.version for item in registry.list_descriptors("test.noop")] == [
        "1.0.0",
        "2.0.0",
    ]


def test_in_memory_store_is_immutable_and_idempotent() -> None:
    store = InMemoryArtifactStore()
    creator = CapabilityRef(name="source.register", version="1.0.0")
    first = store.put(
        artifact_id="requirements/TODO-1/v1",
        artifact_type="RequirementRevision",
        schema_version=1,
        content={"title": "Todo"},
        created_by=creator,
    )
    repeated = store.put(
        artifact_id="requirements/TODO-1/v1",
        artifact_type="RequirementRevision",
        schema_version=1,
        content={"title": "Todo"},
        created_by=creator,
    )

    assert repeated == first
    with pytest.raises(ArtifactImmutableError):
        store.put(
            artifact_id="requirements/TODO-1/v1",
            artifact_type="RequirementRevision",
            schema_version=1,
            content={"title": "Changed"},
            created_by=creator,
        )


def test_file_store_survives_reopen_and_lists_refs(tmp_path: Path) -> None:
    creator = CapabilityRef(name="source.register", version="1.0.0")
    store = FileArtifactStore(tmp_path)
    ref = store.put(
        artifact_id="requirements/TODO-1/v1",
        artifact_type="RequirementRevision",
        schema_version=1,
        content={"title": "Todo"},
        created_by=creator,
    )

    reopened = FileArtifactStore(tmp_path)
    assert reopened.get(ref).content == {"title": "Todo"}
    assert reopened.list_refs() == (ref,)


def test_file_store_detects_content_tampering(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path)
    ref = store.put(
        artifact_id="requirements/TODO-1/v1",
        artifact_type="RequirementRevision",
        schema_version=1,
        content={"title": "Todo"},
        created_by=CapabilityRef(name="source.register", version="1.0.0"),
    )
    path = store.object_path(ref.artifact_id)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["content"]["title"] = "Tampered"
    path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        store.get(ref)


def test_store_context_reads_writes_and_collects_events() -> None:
    context = StoreExecutionContext(InMemoryArtifactStore())
    ref = context.write_artifact(
        artifact_id="validation/TODO-1/v1",
        artifact_type="SpecValidation",
        schema_version=1,
        content={"valid": True},
        created_by=CapabilityRef(name="spec.validate", version="1.0.0"),
    )

    assert context.read_artifact(ref) == {"valid": True}
    assert content_hash({"valid": True}) == ref.content_hash


def test_missing_artifact_raises_specific_error() -> None:
    with pytest.raises(ArtifactNotFoundError):
        InMemoryArtifactStore().get("missing")


def test_registry_descriptor_declares_expected_output_type() -> None:
    descriptor = CapabilityDescriptor(
        name="spec.validate",
        version="1.0.0",
        output_types=(ArtifactTypeRef(name="SpecValidation", schema_version=1),),
    )
    assert descriptor.output_types[0].canonical_name == "SpecValidation@1"
