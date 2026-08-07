from datetime import timedelta

from test_workflow.memory_contracts import (
    Decision,
    MemoryKind,
    MemoryRevision,
    ReadMode,
    RetentionPolicy,
    canonical_sha256,
)
from test_workflow.memory_store import (
    ProgressiveMemoryRetriever,
    RetrievalRequest,
    SQLiteMemoryStore,
)
from tests.memory_contract_fixtures import (
    FIXED_NOW,
    make_namespace,
    make_owner,
    make_owner_acl,
    make_provenance,
    make_source_hash,
)


def test_exact_ref_recall_is_not_limited_by_broad_256_candidate_window(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    namespace = make_namespace()
    owner = make_owner()
    store = SQLiteMemoryStore(
        db_path,
        resolved_sources={"requirement/REQ-1@3": make_source_hash()},
        resolved_evidence=("evidence/EV-1",),
        resolved_benchmarks=("benchmark/M1.0",),
        initial_acl=make_owner_acl(namespace),
    )

    revisions: list[MemoryRevision] = []
    for number in range(257):
        revision = MemoryRevision.create(
            memory_id=f"mem_{number:032x}",
            revision_nonce=f"exact-scale-{number}",
            memory_kind=MemoryKind.SEMANTIC,
            namespace=namespace,
            content={"fact_candidate": f"candidate {number}"},
            provenance=make_provenance(),
            retention_policy=RetentionPolicy(
                policy_ref=f"retention/exact-scale-{number}",
                review_after=FIXED_NOW + timedelta(days=30),
            ),
            formation_event_ref=f"formation/exact-scale-{number}",
            created_by=owner.principal_id,
            idempotency_key=f"idem-exact-scale-{number}",
            created_at=FIXED_NOW + timedelta(seconds=number),
        )
        result = store.append_revision(
            actor=owner,
            revision=revision,
            expected_head_revision_id=None,
            correlation_id=f"create-exact-scale-{number}",
        )
        assert result.decision is Decision.ACCEPTED
        revisions.append(revision)

    target = revisions[-1]
    broad, _cursor = store.query_exact_authorized_namespaces(
        actor=owner,
        namespaces=(namespace,),
        read_mode=ReadMode.ADVISORY,
        now=FIXED_NOW + timedelta(days=1),
        limit=256,
    )
    assert len(broad) == 256
    assert target.ref not in {revision.ref for revision in broad}

    request = RetrievalRequest(
        request_id="exact-scale",
        actor=owner,
        namespaces=(namespace,),
        read_mode=ReadMode.ADVISORY,
        objective_ref="objective/exact-scale",
        objective_digest=canonical_sha256({"objective": "exact-scale"}),
        evaluation_time=FIXED_NOW + timedelta(days=1),
        exact_refs=(target.ref,),
        required_refs=(target.ref,),
        minimum_releases=1,
    )
    result = ProgressiveMemoryRetriever(
        store,
        index=None,
        cursor_key=b"m1b-exact-scale-cursor-key",
    ).retrieve(request)

    assert [released.ref for released in result.released] == [target.ref]
    assert "EXACT_REF_UNRESOLVED" not in result.omitted_reasons
    assert "REQUIRED_REF_UNRESOLVED" not in result.omitted_reasons
