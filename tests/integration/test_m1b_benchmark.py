from test_workflow.memory_store import ProgressiveMemoryRetriever, SQLiteDerivedIndex
from test_workflow.memory_store.benchmark import (
    RetrievalBenchmarkCase,
    RetrievalBenchmarkRunner,
)
from tests.integration.test_m1b_progressive_retrieval import (
    CURSOR_KEY,
    append_promoted,
    make_actor,
    make_project_namespace,
    make_request,
    make_revision,
    make_store,
)
from tests.memory_contract_fixtures import make_namespace, make_owner


def test_reference_profile_meets_m1b_retrieval_thresholds(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()

    live = tuple(
        append_promoted(
            store,
            actor=actor,
            revision=make_revision(
                500 + number,
                actor=actor,
                namespace=namespace,
                text=(
                    f"checkout playwright benchmark relevant {number}"
                    if number <= 3
                    else f"general project memory {number}"
                ),
            ),
        )
        for number in range(1, 6)
    )

    other_actor = make_actor("project-2", "agent-benchmark-secret")
    other_namespace = make_project_namespace("project-2")
    secret = append_promoted(
        store,
        actor=other_actor,
        revision=make_revision(
            506,
            actor=other_actor,
            namespace=other_namespace,
            text="secret checkout benchmark from another project",
        ),
    )
    forgotten = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            507,
            actor=actor,
            namespace=namespace,
            text="forgotten checkout benchmark memory",
        ),
    )

    index = SQLiteDerivedIndex(db_path)
    while index.apply_pending(limit=256):
        pass
    store.revoke_memory(
        actor=actor,
        memory_id=forgotten.memory_id,
        reason_code="BENCHMARK_REVOKE",
        policy_decision_ref="policy/revoke",
        correlation_id="benchmark-revoke",
    )
    store.forget_memory(
        actor=actor,
        memory_id=forgotten.memory_id,
        reason_code="BENCHMARK_FORGET",
        policy_decision_ref="policy/forget",
        correlation_id="benchmark-forget",
    )

    retriever = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
        sync_index=False,
    )
    acceptable = tuple(item.ref for item in live)
    prohibited_unauthorized = (secret.ref,)
    prohibited_forgotten = (forgotten.ref,)
    cases = (
        RetrievalBenchmarkCase(
            case_id="exact-ref",
            request=make_request(
                actor=actor,
                namespace=namespace,
                request_id="benchmark-exact",
                exact_refs=(live[0].ref,),
                required_refs=(live[0].ref,),
            ),
            required_refs=(live[0].ref,),
            acceptable_refs=acceptable,
            unauthorized_refs=prohibited_unauthorized,
            forgotten_refs=prohibited_forgotten,
        ),
        RetrievalBenchmarkCase(
            case_id="keyword-recall",
            request=make_request(
                actor=actor,
                namespace=namespace,
                request_id="benchmark-keyword",
                minimum_releases=3,
                keywords=("checkout", "playwright"),
                required_refs=(live[0].ref, live[1].ref, live[2].ref),
            ),
            required_refs=(live[0].ref, live[1].ref, live[2].ref),
            acceptable_refs=acceptable,
            unauthorized_refs=prohibited_unauthorized,
            forgotten_refs=prohibited_forgotten,
        ),
        RetrievalBenchmarkCase(
            case_id="cross-project-poison",
            request=make_request(
                actor=actor,
                namespace=namespace,
                request_id="benchmark-cross-project",
                keywords=("secret", "checkout"),
            ),
            acceptable_refs=acceptable,
            unauthorized_refs=prohibited_unauthorized,
            forgotten_refs=prohibited_forgotten,
        ),
        RetrievalBenchmarkCase(
            case_id="forgotten-stale-index",
            request=make_request(
                actor=actor,
                namespace=namespace,
                request_id="benchmark-forgotten",
                keywords=("forgotten", "checkout"),
            ),
            acceptable_refs=acceptable,
            unauthorized_refs=prohibited_unauthorized,
            forgotten_refs=prohibited_forgotten,
        ),
    )

    report = RetrievalBenchmarkRunner(retriever).run(
        cases,
        repetitions=3,
        runtime_profile="github-actions-sqlite-reference-small@1",
    )

    assert report.critical_unauthorized_release_count == 0
    assert report.forgotten_content_release_count == 0
    assert report.exact_ref_recall_percent == 100.0
    assert report.required_authority_recall_percent == 100.0
    assert report.noncritical_recall_percent >= 95.0
    assert report.noncritical_precision_percent >= 90.0
    assert report.replay_equivalence_percent == 100.0
    assert report.deterministic_order_percent == 100.0
    assert report.p95_default_latency_ms <= 3000.0
    assert report.p95_hot_latency_ms <= 250.0
    assert report.passed is True
