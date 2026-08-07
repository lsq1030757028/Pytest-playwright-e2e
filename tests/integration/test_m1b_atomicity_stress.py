import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from test_workflow.memory_contracts import Decision
from tests.integration.test_m1b_progressive_retrieval import make_revision
from tests.integration.test_m1b_sqlite_store import make_second_revision, make_store
from tests.memory_contract_fixtures import make_namespace, make_owner


def _append_racing_candidate(item):
    store, revision, gate, owner, expected_head_revision_id = item
    gate.wait()
    return store.compare_and_append_revision(
        actor=owner,
        revision=revision,
        expected_head_revision_id=expected_head_revision_id,
        correlation_id=revision.idempotency_key,
    )


def test_cas_and_outbox_atomicity_across_100_coordinated_races(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    owner = make_owner()
    namespace = make_namespace()
    bootstrap = make_store(db_path)
    left = make_store(db_path)
    right = make_store(db_path)

    for repetition in range(100):
        initial = make_revision(
            10_000 + repetition,
            actor=owner,
            namespace=namespace,
            text=f"atomicity base {repetition}",
        )
        created = bootstrap.append_revision(
            actor=owner,
            revision=initial,
            expected_head_revision_id=None,
            correlation_id=f"atomicity-base-{repetition}",
        )
        assert created.decision is Decision.ACCEPTED

        candidates = (
            make_second_revision(
                initial,
                nonce=f"atomicity-a-{repetition}",
                key=f"idem-atomicity-a-{repetition}",
                value=f"winner candidate A {repetition}",
            ),
            make_second_revision(
                initial,
                nonce=f"atomicity-b-{repetition}",
                key=f"idem-atomicity-b-{repetition}",
                value=f"winner candidate B {repetition}",
            ),
        )
        gate = Barrier(2)
        work = tuple(
            (
                store,
                revision,
                gate,
                owner,
                initial.revision_id,
            )
            for store, revision in zip((left, right), candidates, strict=True)
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(_append_racing_candidate, work))

        decisions = [result.decision for result in results]
        assert decisions.count(Decision.ACCEPTED) == 1
        assert decisions.count(Decision.CONFLICT) == 1
        accepted_index = decisions.index(Decision.ACCEPTED)
        accepted_revision = candidates[accepted_index]

        restarted = make_store(db_path)
        assert restarted.get_head_revision(
            actor=owner,
            memory_id=initial.memory_id,
        ).revision_id == accepted_revision.revision_id
        assert len(
            restarted.list_revision_history(
                actor=owner,
                memory_id=initial.memory_id,
            )
        ) == 2

        with sqlite3.connect(db_path) as connection:
            revision_outbox_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM outbox
                WHERE memory_id = ? AND event_type = 'REVISION_COMMITTED'
                """,
                (initial.memory_id,),
            ).fetchone()[0]
        assert revision_outbox_count == 2

    assert make_store(db_path).verify_event_chain()
