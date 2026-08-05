from datetime import timedelta

import pytest
from pydantic import ValidationError

from test_workflow.memory_contracts import (
    CompatibilityDescriptor,
    CreatorType,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    NamespaceScopeKind,
    Provenance,
    RetentionPolicy,
    TransformationKind,
    canonical_sha256,
)
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_namespace,
    make_provenance,
    make_semantic_revision,
    make_source_hash,
)


def test_canonical_hash_is_key_order_independent_and_storage_metadata_free() -> None:
    left = {"b": 2, "a": {"z": 3, "y": 4}}
    right = {"a": {"y": 4, "z": 3}, "b": 2}

    assert canonical_sha256(left) == canonical_sha256(right)
    assert canonical_sha256({**left, "cache_metadata": "x"}) != canonical_sha256(left)


def test_namespace_canonicalization_and_scope_invariants() -> None:
    namespace = MemoryNamespace(
        organization_id="org-1",
        project_id="project-1",
        scope_kind=NamespaceScopeKind.AGENT,
        scope_id="agent-1",
    )

    assert namespace.canonical == "org/org-1/project/project-1/scope/AGENT/agent-1"
    assert len(namespace.namespace_hash) == 64
    with pytest.raises(ValidationError):
        MemoryNamespace(
            organization_id="org-1",
            project_id=None,
            scope_kind=NamespaceScopeKind.PROJECT,
            scope_id="project-1",
        )


def test_revision_hash_detects_governed_content_drift() -> None:
    revision = make_semantic_revision()
    payload = revision.model_dump(mode="python")
    payload["content"] = {"fact_candidate": "silently changed"}

    with pytest.raises(ValidationError, match="content_hash"):
        MemoryRevision.model_validate(payload)


def test_later_revision_requires_parent_and_immutable_new_id() -> None:
    revision = make_semantic_revision()
    next_revision = MemoryRevision.create(
        memory_id=revision.memory_id,
        revision_nonce="semantic-2",
        revision_number=2,
        parent_revision_refs=(revision.ref,),
        memory_kind=revision.memory_kind,
        namespace=revision.namespace,
        content={"fact_candidate": "The approved timeout is 45 seconds."},
        provenance=revision.provenance,
        retention_policy=revision.retention_policy,
        formation_event_ref="formation/event-2",
        created_by="agent-owner",
        idempotency_key="idem-semantic-2",
        created_at=revision.created_at + timedelta(minutes=1),
    )

    assert next_revision.revision_id != revision.revision_id
    assert next_revision.content_hash != revision.content_hash
    assert next_revision.parent_revision_refs == (revision.ref,)


def test_working_memory_requires_bounded_lifetime() -> None:
    with pytest.raises(ValidationError, match="ttl_seconds"):
        MemoryRevision.create(
            memory_kind=MemoryKind.WORKING,
            namespace=make_namespace(),
            content={"turn_state": "temporary"},
            provenance=make_provenance(),
            retention_policy=RetentionPolicy(policy_ref="retention/working"),
            formation_event_ref="formation/working-1",
            created_by="agent-owner",
            idempotency_key="idem-working-1",
            created_at=FIXED_NOW,
        )


def test_skill_requires_compatibility_and_rejects_embedded_code() -> None:
    source_hash = make_source_hash()
    provenance = Provenance(
        source_refs=("skill/source@1",),
        evidence_refs=("skill/evidence@1",),
        source_content_hashes={"skill/source@1": source_hash},
        created_by_principal="agent-owner",
        creator_type=CreatorType.AGENT,
        capability_or_formation_rule_ref="formation/skill",
        transformation_kind=TransformationKind.SKILL_REGISTRATION,
    )
    compatibility = CompatibilityDescriptor(
        project_architecture_families=("python-web",),
        code_version_range=">=1,<2",
        schema_version_range=">=1,<2",
        capability_version_range="1.x",
        required_permissions=("browser.read",),
        executable_ref="capability://browser-check@1.2.0",
    )

    with pytest.raises(ValidationError, match="unrestricted executable"):
        MemoryRevision.create(
            memory_kind=MemoryKind.SKILL,
            namespace=make_namespace(),
            content={"capability_ref": "browser-check", "shell": "rm -rf /"},
            provenance=provenance,
            compatibility=compatibility,
            retention_policy=RetentionPolicy(policy_ref="retention/skill"),
            formation_event_ref="formation/skill-1",
            created_by="agent-owner",
            idempotency_key="idem-skill-1",
            created_at=FIXED_NOW,
        )


def test_revision_and_provenance_json_are_deeply_immutable() -> None:
    revision = MemoryRevision.create(
        memory_id="mem_22222222222222222222222222222222",
        revision_nonce="immutable-nested",
        memory_kind=MemoryKind.SEMANTIC,
        namespace=make_namespace(),
        content={"nested": {"items": ["one", "two"]}},
        provenance=make_provenance(),
        retention_policy=RetentionPolicy(policy_ref="retention/semantic"),
        formation_event_ref="formation/immutable",
        created_by="agent-owner",
        idempotency_key="idem-immutable",
        created_at=FIXED_NOW,
    )

    with pytest.raises(TypeError, match="immutable"):
        revision.content["nested"] = {"items": ["changed"]}
    with pytest.raises(TypeError):
        revision.content["nested"]["items"][0] = "changed"
    with pytest.raises(TypeError, match="immutable"):
        revision.provenance.source_content_hashes["requirement/REQ-1@3"] = "0" * 64


def test_working_memory_requires_ttl_even_with_campaign_close() -> None:
    with pytest.raises(ValidationError, match="ttl_seconds"):
        MemoryRevision.create(
            memory_kind=MemoryKind.WORKING,
            namespace=make_namespace(),
            content={"turn_state": "temporary"},
            provenance=make_provenance(),
            retention_policy=RetentionPolicy(
                policy_ref="retention/working",
                campaign_close_at=FIXED_NOW + timedelta(hours=1),
            ),
            formation_event_ref="formation/working-campaign",
            created_by="agent-owner",
            idempotency_key="idem-working-campaign",
            created_at=FIXED_NOW,
        )
