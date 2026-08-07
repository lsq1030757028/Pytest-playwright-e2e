import sqlite3

from test_workflow.memory_store import (
    ProgressiveMemoryRetriever,
    RetrievalStatus,
    SQLiteDerivedIndex,
)
from test_workflow.memory_store.recovery import (
    FailClosedRetrievalGateway,
    SQLiteOutboxRecovery,
)
from tests.integration.test_m1b_progressive_retrieval import (
    CURSOR_KEY,
    append_promoted,
    make_request,
    make_revision,
    make_store,
)
from tests.memory_contract_fixtures import make_namespace, make_owner


def test_missing_outbox_revision_event_is_detected_and_reconciled(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    revision = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            301,
            actor=actor,
            namespace=namespace,
            text="reconcile missing outbox revision",
        ),
    )
    index = SQLiteDerivedIndex(db_path)
    while index.apply_pending(limit=256):
        pass

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT sequence
            FROM outbox
            WHERE event_type = 'REVISION_COMMITTED'
              AND payload_json LIKE ?
            """,
            (f"%{revision.revision_id}%",),
        ).fetchone()
        assert row is not None
        missing_sequence = int(row[0])
        connection.execute("DELETE FROM outbox WHERE sequence = ?", (missing_sequence,))
        connection.commit()

    recovery = SQLiteOutboxRecovery(db_path)
    broken = recovery.inspect()
    assert missing_sequence in broken.unreconciled_sequence_gaps
    assert revision.ref in broken.missing_revision_event_refs
    assert broken.healthy is False

    report = recovery.recover()
    assert missing_sequence in report.reconciled_sequence_gaps
    assert revision.ref in report.recreated_revision_events
    assert recovery.inspect().healthy is True

    result = ProgressiveMemoryRetriever(
        store,
        index=SQLiteDerivedIndex(db_path),
        cursor_key=CURSOR_KEY,
    ).retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="outbox-recovered",
            exact_refs=(revision.ref,),
            required_refs=(revision.ref,),
        )
    )
    assert [item.ref for item in result.released] == [revision.ref]


def test_primary_store_outage_fails_closed_without_content(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    store = make_store(db_path)
    actor = make_owner()
    namespace = make_namespace()
    revision = append_promoted(
        store,
        actor=actor,
        revision=make_revision(
            302,
            actor=actor,
            namespace=namespace,
            text="primary outage must fail closed",
        ),
    )
    index = SQLiteDerivedIndex(db_path)
    while index.apply_pending(limit=256):
        pass
    retriever = ProgressiveMemoryRetriever(
        store,
        index=index,
        cursor_key=CURSOR_KEY,
        sync_index=False,
    )

    def unavailable_connection():
        raise sqlite3.OperationalError("primary unavailable")

    store._connect = unavailable_connection  # type: ignore[method-assign]
    result = FailClosedRetrievalGateway(retriever).retrieve(
        make_request(
            actor=actor,
            namespace=namespace,
            request_id="primary-unavailable",
            exact_refs=(revision.ref,),
            required_refs=(revision.ref,),
        )
    )

    assert result.status is RetrievalStatus.BLOCKED
    assert result.released == ()
    assert result.omitted_reasons == ("PRIMARY_STORE_UNAVAILABLE",)
