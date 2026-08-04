from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from test_workflow.harness import (
    ArtifactRef,
    ArtifactTypeRef,
    CapabilityAccess,
    CapabilityDescriptor,
    CapabilityRef,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    ContextLevel,
    ContextRequest,
    ContextSelector,
    DomainEvent,
    ExecutionBudget,
    PermissionScope,
    RetryMode,
    RetryPolicy,
)

HASH = "sha256:" + "a" * 64


def descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name="spec.validate",
        version="1.0.0",
        input_types=(ArtifactTypeRef(name="TestSpec", schema_version=1),),
        output_types=(ArtifactTypeRef(name="SpecValidation", schema_version=1),),
        default_context=ContextRequest(
            level=ContextLevel.FOCUSED,
            selectors=(ContextSelector(namespace="test.spec", keys=("current",)),),
        ),
        required_permissions=PermissionScope(
            read=frozenset({"artifacts/spec/*"}),
            write=frozenset({"artifacts/validation/*"}),
        ),
    )


def artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="spec/TODO-001/v1",
        artifact_type="TestSpec",
        schema_version=1,
        content_hash=HASH,
        source_revisions={"requirement": "REQ-TODO-001@v1"},
        created_by=CapabilityRef(name="source.register", version="1.0.0"),
    )


def test_contract_round_trip_preserves_canonical_identifiers() -> None:
    value = descriptor()
    loaded = CapabilityDescriptor.model_validate_json(value.model_dump_json())
    assert loaded == value
    assert loaded.ref.canonical_name == "spec.validate@1.0.0"
    assert loaded.input_types[0].canonical_name == "TestSpec@1"


def test_descriptor_rejects_invalid_names_versions_and_duplicate_types() -> None:
    with pytest.raises(ValidationError):
        CapabilityDescriptor(name="Spec Validate", version="1.0.0")
    with pytest.raises(ValidationError):
        CapabilityDescriptor(name="spec.validate", version="latest")
    with pytest.raises(ValidationError, match="input artifact types must be unique"):
        CapabilityDescriptor(
            name="spec.validate",
            version="1.0.0",
            input_types=(
                ArtifactTypeRef(name="TestSpec", schema_version=1),
                ArtifactTypeRef(name="TestSpec", schema_version=1),
            ),
        )


def test_descriptor_requires_permissions_for_declared_external_access() -> None:
    with pytest.raises(ValidationError, match="model access requires"):
        CapabilityDescriptor(
            name="ai.propose-test-spec",
            version="1.0.0",
            access=CapabilityAccess(allow_model=True),
        )
    with pytest.raises(ValidationError, match="network access requires"):
        CapabilityDescriptor(
            name="target.materialize",
            version="1.0.0",
            access=CapabilityAccess(allow_network=True),
        )


def test_context_and_permission_scopes_reject_unsafe_wildcards() -> None:
    with pytest.raises(ValidationError, match="explicit and safe"):
        ContextSelector(namespace="source.registry", keys=("*",))
    with pytest.raises(ValidationError, match="trailing"):
        PermissionScope(read=frozenset({"artifacts/*/secret"}))
    with pytest.raises(ValidationError, match="cannot contain"):
        PermissionScope(write=frozenset({"../outside"}))


def test_artifact_reference_rejects_path_escape_and_bad_hash() -> None:
    base = {
        "artifact_type": "TestSpec",
        "schema_version": 1,
        "created_by": CapabilityRef(name="source.register", version="1.0.0"),
    }
    with pytest.raises(ValidationError, match="safe relative"):
        ArtifactRef(artifact_id="spec/../secret", content_hash=HASH, **base)
    with pytest.raises(ValidationError):
        ArtifactRef(artifact_id="spec/TODO-1", content_hash="abc", **base)


def test_request_rejects_duplicate_artifact_ids() -> None:
    with pytest.raises(ValidationError, match="input artifact ids must be unique"):
        CapabilityRequest(
            request_id="req-1",
            capability=descriptor().ref,
            input_artifacts=(artifact(), artifact()),
        )


def test_result_status_invariants_are_enforced() -> None:
    with pytest.raises(ValidationError, match="successful result"):
        CapabilityResult(
            request_id="req-1",
            status=CapabilityResultStatus.SUCCESS,
            blockers=("not allowed",),
        )
    with pytest.raises(ValidationError, match="failed result requires"):
        CapabilityResult(request_id="req-1", status=CapabilityResultStatus.FAILED)
    with pytest.raises(ValidationError, match="blocked result requires"):
        CapabilityResult(request_id="req-1", status=CapabilityResultStatus.BLOCKED)


def test_retry_policy_rejects_incoherent_shapes() -> None:
    with pytest.raises(ValidationError, match="requires max_attempts=1"):
        RetryPolicy(mode=RetryMode.NONE, max_attempts=2)
    with pytest.raises(ValidationError, match="at least two attempts"):
        RetryPolicy(mode=RetryMode.FIXED, max_attempts=1)


def test_domain_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DomainEvent(
            event_id="event-1",
            event_type="capability.completed",
            occurred_at=datetime(2026, 8, 5),
            source=descriptor().ref,
        )

    event = DomainEvent(
        event_id="event-2",
        event_type="capability.completed",
        occurred_at=datetime(2026, 8, 5, tzinfo=UTC),
        source=descriptor().ref,
    )
    assert event.occurred_at.utcoffset() is not None


def test_execution_budget_is_non_negative() -> None:
    with pytest.raises(ValidationError):
        ExecutionBudget(model_calls=-1)
